package library;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.FileReader;
import java.io.IOException;
/**
* Manages patrons
*
*@author Isaac Elizarraraz
*@version 1.0
*@since 1.0
*@license.agreement Gnu General Public License 3.0
*/
public class Patron{
	/**
	* Creates a new patron
	*
	*@param name  			The name of the patron
	*@param email 			The patrons email
	*@since 1.0
	*/
	public Patron(String name, String email){
		this.name = name;
		this.email = email;
	}
	/**
	* Returns the patrons information
	*
	*@since 1.0
	*/
	public Patron(BufferedReader br)throws IOException{
			String line = br.readLine();
			this.name = line;
			
			line = br.readLine();
			this.email = line;
	}
	public void save(BufferedWriter bw)throws IOException{
			bw.write(name + '\n');
			bw.write(email + '\n');
			
	}		
	@Override
	public String toString(){
		return name + " (" + email + ")";
	}
	
	private String name;
	private String email;
}
