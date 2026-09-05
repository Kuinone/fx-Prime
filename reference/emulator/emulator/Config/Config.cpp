#include "Config.hpp"
#include <fstream>
#include <imgui.h>
#include <string>
#include <vector>

static bool FileReadable(const std::string &path) {
    std::ifstream fin(path);
    return fin.good();
}

void EmuConfig::initTranslate(){
    translate[UI_TITLE]="CasioEmuNeo";
    translate[UI_DISAS]="Disassembler";
    translate[UI_DISAS_WAITING]="Please wait ...";
    translate[UI_DISAS_GOTO_ADDR]="go to addr: ";
    translate[UI_DISAS_STEP]="step";
    translate[UI_DISAS_TRACE]="trace";
    translate[UI_REPORT_WINDOW]="Watch Window";
    translate[UI_REPORT_RANGE]="set stack range";
    translate[UI_REPORT_RANGE_SLIDER]="range";
    translate[UI_STACK]="Stack Window";
    translate[UI_INJECTOR]="Injector";
    translate[UI_CHANGE_SCALE]="Change Scale";
    translate[UI_CHANGE_SCALE_SLIDER]="scale";
    translate[UI_ROP_INPUT]="Input your rop!";
    translate[UI_ROP_SETINPUTRANGE]="Set rop size";
    translate[UI_ROP_ANOFFSET]="set 'an' offset bytes";
    translate[UI_ROP_ENTERAN]="Enter 'an'";
    translate[UI_ROP_LOAD]="Load ROP";
    translate[UI_ROP_LOADFROMSTR]="Load ROP from string";
    translate[UI_INFO1]="Calculator is already set to Math I/O mode!";
    translate[UI_INFO2]="'an' is entered!\nPlease make sure you're in Math I/O mode\n Back to emulator and press [->][=] to finish!";
    translate[UI_INFO3]="ROP is entered!\nPlease press [->][=] to finish!";
    translate[UI_MEMEDIT]="Memory Viewer";
    translate[UI_REGS_BREAK_HINT] = "Please view registers while at a breakpoint";
    translate[UI_BP_SELECT_MODE] = "Select breakpoint mode:";
    translate[UI_BP_FIND_READ] = "Find what reads this address";
    translate[UI_BP_FIND_WRITE] = "Find what writes to this address";
    translate[UI_BP_DELETE] = "Delete this address";
    translate[UI_BP_NOT_SET] = "No breakpoints set. Add an address, right-click it, and select a mode.";
    translate[UI_BP_LISTENING] = "Listening on address: %04x";
    translate[UI_BP_CLEAR_RECORDS] = "Clear records";
    translate[UI_BP_ADDR] = "Address:";
    translate[UI_BP_ADD_ADDR] = "Add address";
    translate[UI_BP_MODE] = "Mode:";
    translate[UI_BP_WRITE] = "Write";
    translate[UI_BP_READ] = "Read";
    translate[UI_MEM_BP] = "Memory Breakpoint";
    translate[UI_GUIDE_WINDOW_TITLE] = "CasioEmuNeo - First Run Setup";
    translate[UI_GUIDE_TITLE] = "Startup Guide";
    translate[UI_GUIDE_LINE1] = "No valid model/ROM configuration was found.";
    translate[UI_GUIDE_LINE2] = "Please enter a model directory path (it must include model.lua and ROM file). Example: models/fx991cnx";
    translate[UI_GUIDE_INPUT_LABEL] = "Model directory";
    translate[UI_GUIDE_BTN_BROWSE] = "Browse...";
    translate[UI_GUIDE_BTN_DEFAULT] = "Use default";
    translate[UI_GUIDE_BTN_CONFIRM] = "Confirm and continue";
    translate[UI_GUIDE_BTN_EXIT] = "Exit";
    translate[UI_GUIDE_PICK_FAILED] = "Failed to open desktop directory picker: ";
    translate[UI_GUIDE_PICK_NOT_AVAILABLE] = "No supported desktop directory picker found (zenity/kdialog).";
    translate[UI_GUIDE_PICK_CANCELLED] = "No directory selected.";
    translate[UI_GUIDE_NO_SELECTION_ERROR] = "No valid model selected.";
    translate[UI_GUIDE_PICKER_TITLE] = "Select model directory";
}

void EmuConfig::update(){
    file->write(root);
}

void EmuConfig::loadTranslate(std::string path){
    std::ifstream fin(path);
    if(fin.fail())
        return;
    char buf[200] = {0};
    int ss = 0;
    while (!fin.eof()) {
        fin.getline(buf,199);
        for (int i = 0; i < 100 && buf[i]; i++) {
            if(buf[i]=='%')
                buf[i]='\n';
        }
        fbuilder.AddText(buf);
        translate[ss] = std::string(buf);
        
        ss++;
    }
    fin.close();
}

EmuConfig::EmuConfig(const char *f){
    initTranslate();
    path = f;
    file = new mINI::INIFile(path);
    if(!file->read(root))
        return;
    format_succ = true;
    if(root.has("lang")){
        auto& lang = root["lang"];
        if(lang.has("lang")){
            std::string prefix = lang["lang"];
            loadTranslate("lang/"+prefix+".ini");
        }
    }

}

std::string EmuConfig::GetFontPath(){
    if(root.has("settings")){
        if(root["settings"].has("font")){
            return root["settings"]["font"];
        }
    }
    return "unifont.otf";
}

std::string EmuConfig::GetUsableFontPath(){
    std::string configured = GetFontPath();
    if(FileReadable(configured))
        return configured;

    std::vector<std::string> font_candidates = {
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    };

    for(const auto &candidate : font_candidates){
        if(FileReadable(candidate))
            return candidate;
    }

    return configured;
}

std::string EmuConfig::GetModulePath(){
    if(root.has("settings")){
        if(root["settings"].has("model")){
            return root["settings"]["model"];
        }
    }
    return "991cnx";
}

void EmuConfig::SetModulePath(const std::string &path){
    root["settings"]["model"] = path;
    update();
}

float EmuConfig::GetScale(){
    if(!root.has("settings"))
        return 1.0;
    if(!root["settings"].has("scale"))
        return 1.0;
    return std::stof(root["settings"]["scale"]);
}

void EmuConfig::SetScale(float num){
    root["settings"]["scale"] = std::to_string(num);
    update();
}

char* EmuConfig::operator[](int idx){
    return translate[idx].data();
}

ImFontGlyphRangesBuilder& EmuConfig::GetAtlas(){
    return fbuilder;
}

EmuConfig EmuGloConfig("config.ini");