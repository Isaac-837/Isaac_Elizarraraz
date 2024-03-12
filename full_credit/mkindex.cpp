#include <iostream>
#include <sstream>
#include <fstream>
#include "Index.h"
#include "Location.h"
int main(int arc, char* argv[]){
    Index index;
    std::string word;
    std::string text;

    for(int i = 1; i < arc; i++){
        std::string filename{argv[i]};
        std::ifstream ifs{filename};
        int line = 0;
        if (!ifs) throw std::runtime_error{"failed to open file"};
        std::string s;

        while(ifs){
            std::getline(ifs, text);
            ++line;
            if(text.empty()){
                continue;
            }
            std::istringstream iss{text};
            while(iss){
                iss >> word;
                try{
                    while(!word.empty()){
                        if(!isalpha(word.front())){
                            word.erase(0,1);
                        } else break;
                    }
                    while(!word.empty()){
                        if(!isalpha(word.back())){
                            word.pop_back();
                        } else break;
                    }
                    if(!word.empty()){
                        for(char& c : word){
                            c = tolower(c);
                            index.add_word(word, filename, line);
                        }
                    } 
                }catch(...){std::cerr << "invalid word" << std::endl;};
            }
        }
    }
    std::cout << index << std::endl;
    return 0;
} 
   