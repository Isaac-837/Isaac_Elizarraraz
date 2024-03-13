#include <iomanip>
#include "Index.h"
#include "Location.h"

void Index::add_word(Word word, std::string filename, int line){
    //if this word has not appeared add it to the keys
    if(_index.count(word) == 0){
        _index[word] = Locations{};
    }
    //add the location for this word into the map
    _index[word].insert(Location{filename, line});
}
//print the index for every word, the filename and the line number
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