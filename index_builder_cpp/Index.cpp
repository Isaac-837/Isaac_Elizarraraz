#include <iomanip>
#include "Index.h"
#include "Location.h"

void Index::add_word(Word word, std::string filename, int line){
    
    if(_index.count(word) == 0){
        _index[word] = Locations{};
    }
    _index[word].insert(Location{filename, line});
}

std::ostream& operator<<(std::ostream& ost, const Index& index){
    ost << "Index\n=====\n";
    for(const auto& [word, locations] : index._index){
        ost << word << ": ";
        for(const auto& location : locations){
            ost << location << ", ";
        }
        ost << std::endl;
    }
    return ost;
}