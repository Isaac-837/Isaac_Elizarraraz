#include <iomanip>
#include "Location.h"

Location::Location(std::string filename, int line)
    : _filename{filename}, _line{line} {}
int Location::compare(const Location& location) const{
    if(_filename < location._filename){
        return -1;
    }
    if(_filename > location._filename){
        return 1;
    }
    return _line - location._line;
}
std::ostream& operator<<(std::ostream& ost, const Location& location){
    ost << location._filename << " line " << location._line;
    return ost;
}