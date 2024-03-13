#include <iostream>
#include <sstream>
#include <fstream>
#include "Index.h"
#include "Location.h"
int main(int arc, char* argv[]){
    Index index;
    std::string word;
    std::string text;
//iterate through every file given as a parameter
    for(int i = 1; i < arc; i++){
        std::string filename{argv[i]};
        std::ifstream ifs{filename};
        int line = 0;
        if (!ifs) throw std::runtime_error{"failed to open file"};
        std::string s;
        //read through the file line by line
        while(ifs){
            std::getline(ifs, text);
            ++line;
            //check if you have reached the end for every line
            if(text.empty()){
                continue;
            }
            std::istringstream iss{text};
            //read through every lines words
            while(iss){
                iss >> word;
                try{
                    //remove non alpabet charachters from the front, back, then put each letter of the word in lowercase
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
   