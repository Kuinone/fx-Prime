#include "Config.hpp"
#include "Config/Config.hpp"
#include "Gui/imgui_impl_sdl2.h"
#include "Gui/imgui_impl_sdlrenderer2.h"
#include "Gui/Ui.hpp"
#include "SDL_stdinc.h"
#include "SDL_thread.h"
#include "SDL_timer.h"
#include "utils.h"

#include "imgui.h"

#include <SDL.h>
#include <SDL_image.h>
#include <cstdint>
#include <iostream>
#include <iterator>
#include <ostream>
#include <ratio>
#include <thread>
#include <string>
#include <map>
#include <mutex>
#include <atomic>
#include <condition_variable>

#include "Emulator.hpp"
#include "Logger.hpp"
#include "Data/EventCode.hpp"
#include "SDL_events.h"
#include "SDL_keyboard.h"
#include "SDL_mouse.h"
#include "SDL_video.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>

#include <unistd.h>
#include <csignal>

static bool abort_flag = false;
static std::atomic<bool> mem_spans_watcher_running(false);
static std::thread mem_spans_watcher_thread;

static std::string Trim(const std::string &value)
{
	size_t start = 0;
	while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start])))
		++start;

	size_t end = value.size();
	while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1])))
		--end;

	return value.substr(start, end - start);
}

static bool TryRunPickCommand(const std::string &command, std::string *picked_path, std::string *error)
{
	FILE *pipe = popen(command.c_str(), "r");
	if (!pipe)
	{
		if (error)
			*error = "popen failed";
		return false;
	}

	char buffer[1024];
	std::string output;
	while (fgets(buffer, sizeof(buffer), pipe) != nullptr)
		output += buffer;

	int rc = pclose(pipe);
	output = Trim(output);

	if (rc != 0)
	{
		if (error)
			*error = output.empty() ? ("command exited with code " + std::to_string(rc)) : output;
		return false;
	}

	if (output.empty())
	{
		if (error)
			*error = "empty selection";
		return false;
	}

	if (picked_path)
		*picked_path = output;
	return true;
}

static bool TryPickDirectoryWithDesktopDialog(std::string *picked_path, std::string *error)
{
	const bool has_display = std::getenv("DISPLAY") != nullptr || std::getenv("WAYLAND_DISPLAY") != nullptr;
	if (!has_display)
	{
		if (error)
			*error = "No GUI display available";
		return false;
	}

	std::string title = EmuGloConfig[UI_GUIDE_PICKER_TITLE];
	std::string cmd_zenity = "zenity --file-selection --directory --title=\"" + title + "\"";
	if (TryRunPickCommand(cmd_zenity, picked_path, error))
		return true;

	std::string cmd_kdialog = "kdialog --getexistingdirectory \"$PWD\" --title \"" + title + "\"";
	if (TryRunPickCommand(cmd_kdialog, picked_path, error))
		return true;

	if (error && error->empty())
		*error = "No supported picker found";
	return false;
}

static std::string JoinPath(const std::string &base, const std::string &name)
{
	if (base.empty())
		return name;
	if (base.back() == '/')
		return base + name;
	return base + "/" + name;
}

static bool ExtractRomPathFromModel(const std::string &model_path, std::string *rom_path, std::string *error)
{
	auto model_lua_path = JoinPath(model_path, "model.lua");
	if (!casioemu::FileSystem::exists(model_lua_path))
	{
		if (error)
			*error = "Missing model.lua in selected model directory";
		return false;
	}

	lua_State *lua_state = luaL_newstate();
	luaL_openlibs(lua_state);
	std::string rom_path_value;

	lua_pushlightuserdata(lua_state, &rom_path_value);
	lua_pushcclosure(lua_state, [](lua_State *lua_state) {
		auto *rom_path_value = static_cast<std::string *>(lua_touserdata(lua_state, lua_upvalueindex(1)));
		int model_table_idx = lua_gettop(lua_state) >= 2 && lua_istable(lua_state, 2) ? 2 : 1;
		if (!lua_istable(lua_state, model_table_idx))
			return luaL_error(lua_state, "emu.model expects a table argument");

		lua_getfield(lua_state, model_table_idx, "rom_path");
		if (!lua_isstring(lua_state, -1))
		{
			lua_pop(lua_state, 1);
			return luaL_error(lua_state, "model.rom_path is missing or not a string");
		}

		*rom_path_value = lua_tostring(lua_state, -1);
		lua_pop(lua_state, 1);
		return 0;
	}, 1);

	lua_newtable(lua_state);
	lua_pushvalue(lua_state, -2);
	lua_setfield(lua_state, -2, "model");
	lua_setglobal(lua_state, "emu");
	lua_pop(lua_state, 1);

	if (luaL_loadfile(lua_state, model_lua_path.c_str()) != LUA_OK)
	{
		if (error)
			*error = lua_tostring(lua_state, -1);
		lua_close(lua_state);
		return false;
	}

	if (lua_pcall(lua_state, 0, 0, 0) != LUA_OK)
	{
		if (error)
			*error = lua_tostring(lua_state, -1);
		lua_close(lua_state);
		return false;
	}

	lua_close(lua_state);

	if (rom_path_value.empty())
	{
		if (error)
			*error = "rom_path is missing in model.lua";
		return false;
	}

	if (rom_path)
		*rom_path = rom_path_value;
	return true;
}

static bool ValidateModelPath(const std::string &model_path, std::string *error)
{
	if (model_path.empty())
	{
		if (error)
			*error = "Model path is empty";
		return false;
	}

	std::string rom_relative_path;
	if (!ExtractRomPathFromModel(model_path, &rom_relative_path, error))
		return false;

	auto rom_full_path = JoinPath(model_path, rom_relative_path);
	if (!casioemu::FileSystem::exists(rom_full_path))
	{
		if (error)
			*error = "ROM file not found: " + rom_full_path;
		return false;
	}

	return true;
}

static bool PromptModelSelectionGuide(std::string &model_path, std::string *error)
{
	SDL_Window *guide_window = SDL_CreateWindow(
		EmuGloConfig[UI_GUIDE_WINDOW_TITLE],
		SDL_WINDOWPOS_CENTERED,
		SDL_WINDOWPOS_CENTERED,
		760,
		280,
		SDL_WINDOW_SHOWN
	);
	if (!guide_window)
	{
		if (error)
			*error = SDL_GetError();
		return false;
	}

	SDL_Renderer *guide_renderer = SDL_CreateRenderer(guide_window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
	if (!guide_renderer)
	{
		if (error)
			*error = SDL_GetError();
		SDL_DestroyWindow(guide_window);
		return false;
	}

	IMGUI_CHECKVERSION();
	ImGui::CreateContext();
	ImGui::StyleColorsDark();
	{
		ImGuiIO &io = ImGui::GetIO();
		auto font_path = EmuGloConfig.GetUsableFontPath();
		if (io.Fonts->AddFontFromFileTTF(
			font_path.c_str(),
			16.0f,
			nullptr,
			io.Fonts->GetGlyphRangesChineseFull()
		) == nullptr)
		{
			io.Fonts->AddFontDefault();
			SDL_Log("Failed to load guide font '%s', fallback to default ImGui font.", font_path.c_str());
		}
		io.Fonts->Build();
	}
	ImGui_ImplSDL2_InitForSDLRenderer(guide_window, guide_renderer);
	ImGui_ImplSDLRenderer2_Init(guide_renderer);

	char model_path_buffer[1024] = {0};
	auto initial_path = model_path.empty() ? std::string("models/fx991cnx") : model_path;
	strncpy(model_path_buffer, initial_path.c_str(), sizeof(model_path_buffer) - 1);

	bool running = true;
	bool selected = false;
	std::string local_error;

	while (running)
	{
		SDL_Event event;
		while (SDL_PollEvent(&event))
		{
			ImGui_ImplSDL2_ProcessEvent(&event);
			if (event.type == SDL_QUIT)
				running = false;
			if (event.type == SDL_WINDOWEVENT && event.window.windowID == SDL_GetWindowID(guide_window) && event.window.event == SDL_WINDOWEVENT_CLOSE)
				running = false;
		}

		ImGui_ImplSDLRenderer2_NewFrame();
		ImGui_ImplSDL2_NewFrame();
		ImGui::NewFrame();

		ImGui::SetNextWindowPos(ImVec2(0, 0));
		ImGui::SetNextWindowSize(ImVec2(760, 280));
		ImGui::Begin(EmuGloConfig[UI_GUIDE_TITLE], nullptr, ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoCollapse);
		ImGui::TextWrapped("%s", EmuGloConfig[UI_GUIDE_LINE1]);
		ImGui::TextWrapped("%s", EmuGloConfig[UI_GUIDE_LINE2]);
		ImGui::Spacing();
		ImGui::InputText(EmuGloConfig[UI_GUIDE_INPUT_LABEL], model_path_buffer, sizeof(model_path_buffer));
		if (ImGui::Button(EmuGloConfig[UI_GUIDE_BTN_BROWSE]))
		{
			std::string picked_path;
			std::string pick_error;
			if (TryPickDirectoryWithDesktopDialog(&picked_path, &pick_error))
			{
				strncpy(model_path_buffer, picked_path.c_str(), sizeof(model_path_buffer) - 1);
				model_path_buffer[sizeof(model_path_buffer) - 1] = '\0';
				local_error.clear();
			}
			else
			{
				if (pick_error == "empty selection")
					local_error = EmuGloConfig[UI_GUIDE_PICK_CANCELLED];
				else if (pick_error == "No supported picker found" || pick_error == "No GUI display available")
					local_error = EmuGloConfig[UI_GUIDE_PICK_NOT_AVAILABLE];
				else
					local_error = std::string(EmuGloConfig[UI_GUIDE_PICK_FAILED]) + pick_error;
			}
		}
		ImGui::SameLine();
		if (ImGui::Button(EmuGloConfig[UI_GUIDE_BTN_DEFAULT]))
		{
			strncpy(model_path_buffer, "models/fx991cnx", sizeof(model_path_buffer) - 1);
			model_path_buffer[sizeof(model_path_buffer) - 1] = '\0';
			local_error.clear();
		}
		ImGui::SameLine();
		if (ImGui::Button(EmuGloConfig[UI_GUIDE_BTN_CONFIRM]))
		{
			std::string candidate = Trim(std::string(model_path_buffer));
			std::string validation_error;
			if (ValidateModelPath(candidate, &validation_error))
			{
				model_path = candidate;
				selected = true;
				running = false;
			}
			else
			{
				local_error = validation_error;
			}
		}
		ImGui::SameLine();
		if (ImGui::Button(EmuGloConfig[UI_GUIDE_BTN_EXIT]))
			running = false;

		if (!local_error.empty())
			ImGui::TextColored(ImVec4(1.0f, 0.45f, 0.45f, 1.0f), "%s", local_error.c_str());
		ImGui::End();

		ImGui::Render();
		SDL_SetRenderDrawColor(guide_renderer, 20, 20, 20, 255);
		SDL_RenderClear(guide_renderer);
		ImGui_ImplSDLRenderer2_RenderDrawData(ImGui::GetDrawData());
		SDL_RenderPresent(guide_renderer);
		SDL_Delay(16);
	}

	ImGui_ImplSDLRenderer2_Shutdown();
	ImGui_ImplSDL2_Shutdown();
	ImGui::DestroyContext();
	SDL_DestroyRenderer(guide_renderer);
	SDL_DestroyWindow(guide_window);

	if (!selected)
	{
		if (error)
			*error = EmuGloConfig[UI_GUIDE_NO_SELECTION_ERROR];
		return false;
	}

	return true;
}

void StartMemSpansConfigWatcherThread(const std::string &path);
void StopMemSpansConfigWatcherThread();

using namespace casioemu;


// #define DEBUG
int main(int argc, char *argv[])
{
	std::map<std::string, std::string> argv_map;
	bool model_from_cli = false;
	for (int ix = 1; ix != argc; ++ix)
	{
		std::string key, value;
		char *eq_pos = strchr(argv[ix], '=');
		if (eq_pos)
		{
			key = std::string(argv[ix], eq_pos);
			value = eq_pos + 1;
		}
		else
		{
			key = "model";
			value = argv[ix];
		}

		if (argv_map.find(key) == argv_map.end())
			argv_map[key] = value;
		else
			logger::Info("[argv] #%i: key '%s' already set\n", ix, key.c_str());

		if (key == "model")
			model_from_cli = true;
	}

	if (argv_map.find("model") == argv_map.end())
	{

#ifdef DEBUG
		argv_map["model"]="E:/projects/CasioEmuX/models/fx991cncw";
#else
		argv_map["model"]=EmuGloConfig.GetModulePath();
#endif
		// printf("No model path supplied\n");
		// exit(2);
	}
	argv_map["script"]="lua-common.lua";

	std::string model_validation_error;
	if (!ValidateModelPath(argv_map["model"], &model_validation_error))
	{
		if (model_from_cli)
			PANIC("Invalid model path from command line: %s\n", model_validation_error.c_str());

		std::string selected_model_path = argv_map["model"];
		std::string guide_error;
		if (!PromptModelSelectionGuide(selected_model_path, &guide_error))
			PANIC("No valid model selected. %s\n", guide_error.c_str());

		argv_map["model"] = selected_model_path;
		EmuGloConfig.SetModulePath(selected_model_path);
	}

	int sdlFlags = SDL_INIT_VIDEO | SDL_INIT_TIMER;
	if (SDL_Init(sdlFlags) != 0)
		PANIC("SDL_Init failed: %s\n", SDL_GetError());

	int imgFlags = IMG_INIT_PNG;
	if (IMG_Init(imgFlags) != imgFlags)
		PANIC("IMG_Init failed: %s\n", IMG_GetError());

	std::string history_filename;
	auto history_filename_iter = argv_map.find("history");
	if (history_filename_iter != argv_map.end())
		history_filename = history_filename_iter->second;

	if (!history_filename.empty())
	{
		
	}

    for (auto s: {SIGTERM, SIGINT}) {
        signal(s, [](int) {
            abort_flag = true;
        });
    }
	// while(1)
	// 	;


	{
		Emulator emulator(argv_map);
		// Note: argv_map must be destructed after emulator.

        // start colored spans file watcher thread
    	auto colored_spans_file = emulator.GetModelFilePath("mem-spans.txt");
		DebugUi::UpdateMarkedSpans({});
        StartMemSpansConfigWatcherThread(colored_spans_file);

		DebugUi ui;
	
		while (emulator.Running())
		{
			ui.PaintUi();
			ui.PaintSDL();

			SDL_Event event;
			if (!SDL_WaitEventTimeout(&event, 16))
				continue;
			
            if (abort_flag) {
                abort_flag = false;
                SDL_Event ev_exit;
                SDL_zero(ev_exit);
                ev_exit.type = SDL_WINDOWEVENT;
                ev_exit.window.event = SDL_WINDOWEVENT_CLOSE;
                SDL_PushEvent(&ev_exit);
            }
			//ui.PaintSDL();
			switch (event.type)
			{
			case SDL_USEREVENT:
				switch (event.user.code)
				{
				case CE_FRAME_REQUEST:
					emulator.Frame();
					
					break;
				case CE_EMU_STOPPED:
					if (emulator.Running())
						PANIC("CE_EMU_STOPPED event received while emulator is still running\n");
					break;
				
				}
				break;
			case SDL_WINDOWEVENT:
				switch (event.window.event)
				{
				case SDL_WINDOWEVENT_CLOSE:
					emulator.Shutdown();
					break;
				case SDL_WINDOWEVENT_RESIZED:
					 if (!emulator.IsResizable())
					 {
					 	// Normally, in this case, the window manager should not
					 	// send resized event, but some still does (such as xmonad)
					 	break;
					 }
					
					//ImGui_ImplSDL2_ProcessEvent(&event);
					if(event.window.windowID == SDL_GetWindowID(emulator.window)){
					emulator.WindowResize(event.window.data1, event.window.data2);
					}
					break;
				case SDL_WINDOWEVENT_EXPOSED:
					emulator.Repaint();
					break;
				}
				break;

			case SDL_MOUSEBUTTONDOWN:
			case SDL_MOUSEBUTTONUP:
			case SDL_KEYDOWN:
			case SDL_KEYUP:
			case SDL_TEXTINPUT:
			case SDL_MOUSEMOTION:
			case SDL_MOUSEWHEEL:
				ImGui_ImplSDL2_ProcessEvent(&event);
				if(SDL_GetKeyboardFocus()!=emulator.window && SDL_GetMouseFocus()!=emulator.window)
				{
					break;
				}
				emulator.UIEvent(event);
				
				break;
			}
			

		
		}

		StopMemSpansConfigWatcherThread();

		
		//console_input_thread.join();
	}

	std::cout << '\n';
	
	IMG_Quit();
	SDL_Quit();
	
	if (!history_filename.empty())
	{
		
	}

	return 0;
}

#define MEM_SPANS_CONFIG_POLLING_INTERVAL 1 /* seconds */
void StartMemSpansConfigWatcherThread(const std::string &path) {
	StopMemSpansConfigWatcherThread();
	mem_spans_watcher_running.store(true);
	mem_spans_watcher_thread = std::thread([path]() {
        uint64_t last_mtime{};
        // Currently we just use this naive file modification watcher (periodically polling method).
        // There are platform-dependent methods (like inotify on *nix)
        // but they're more efficient for folders/bunch of files; if just for a single file,
        // the performance impact can be considered *negligible*.
#pragma clang diagnostic push
#pragma ide diagnostic ignored "EndlessLoop"
        // loop during the whole program lifetime
		while (mem_spans_watcher_running.load()) {
            if (FileSystem::exists(path)) {
                auto mtime = FileSystem::mtime_ms(path);
                if (mtime != last_mtime) {
                    DebugUi::UpdateMarkedSpans(casioemu::ParseColoredSpansConfig(path));
                    last_mtime = mtime;
                }
            } else {
                DebugUi::UpdateMarkedSpans({});
                last_mtime = 0L;
            }
            sleep(MEM_SPANS_CONFIG_POLLING_INTERVAL);
        }
#pragma clang diagnostic pop
	});
}

void StopMemSpansConfigWatcherThread() {
	mem_spans_watcher_running.store(false);
	if (mem_spans_watcher_thread.joinable()) {
		mem_spans_watcher_thread.join();
	}
}
