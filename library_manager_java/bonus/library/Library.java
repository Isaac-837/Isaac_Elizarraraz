package library;
import java.util.ArrayList;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.FileReader;
import java.io.IOException;

/**
* Creates a Library Menu with publications and patrons
*
*@author Isaac Elizarraraz
*@version 1.0
*@since 1.0
*@license.agreement Gnu General Public License 3.0
*/

public class Library {
	
	/**
	* Takes a name for a new Library
	*@since 1.0
	*/
	
	public Library(String name){
		this.name = name;
	}
	public Library(BufferedReader br) throws IOException{
		String line = br.readLine();
		this.name = line;
		line = br.readLine();
		int size = Integer.parseInt(line);
		publications.clear();
		patrons.clear();
		
		for(int i = 0; i < size; i++){
		//System.out.println(line);
			line = br.readLine();
			if(line.equals("Publication")){
				Publication copyPublication = new Publication(br);
				publications.add(copyPublication);
			}
			else{
				Publication copyVideo = new Video(br);
				publications.add(copyVideo);
			}
		}
		line = br.readLine();
		size = Integer.parseInt(line);
		
		for(int i = 0; i < size; i++){
			line = br.readLine();
			Patron copyPatron = new Patron(br);
			patrons.add(copyPatron);
		}
		//System.out.println(publications.toString());
		//this.publications = new ArrayList<Publication>(savedPublications);
		//this.patrons = new ArrayList<Patron>(savedPatrons);
	}

	public void save(BufferedWriter bw) throws IOException{
		bw.write(name + '\n');
		bw.write("" + publications.size() + '\n');
		for(int i = 0; i < publications.size(); i++){
			if(publications.get(i) instanceof Video){
				bw.write("Video" + '\n');
				publications.get(i).save(bw);
			}
			else if(publications.get(i) instanceof Publication){
				bw.write("Publication" + '\n');
				publications.get(i).save(bw);
			}
		}
		bw.write("" + patrons.size() + '\n');
		for(int i = 0; i < patrons.size(); i++){
			bw.write("Patron" + '\n');
			patrons.get(i).save(bw);		
		}
		bw.close();
	}
	/**
	* Adds a new publication to the Library
	*
	*@param publication  			The desired publication to add
	*@since 1.0
	*/
	public void addPublication(Publication publication){
		publications.add(publication);
		
	}
	/**
	* Adds a patron to the Library
	*
	*@param patron  			The desired patron to add
	*@since 1.0
	*/
	public void addPatron(Patron patron){
		patrons.add(patron);
		
	}
	/**
	* Checks out an existing publication from the Library
	*
	*@param publicationIndex    			The chosen Publication to check out
	*@param patronIndex         			The Patron checking out a publication
	*@since 1.0
	*/
	public void checkOut(int publicationIndex, int patronIndex){
		if((publicationIndex < 0) || (publicationIndex > publications.size() + 1)){
			System.err.println("Invalid book selection");
			System.exit(-1);
		}
		if((patronIndex < 0) || (patronIndex > patrons.size() + 1)){
			System.err.println("Invalid patron selection");
			System.exit(-1);
		}
			publications.get(publicationIndex).checkOut(patrons.get(patronIndex));
		
	}
	/**
	* Checks in a publication that is currently checked out
	*
	*@param publicationIndex    			The publication to check in
	*@since 1.1
	*/
	
	public void checkIn(int publicationIndex){
		if((publicationIndex < 0) || (publicationIndex > publications.size() + 1)){
			System.err.println("Invalid selection");
			System.exit(-1);
		}
			publications.get(publicationIndex).checkIn();
		
	}
	/**
	* Creates a menu with all patrons
	*
	*@since 1.0
	*/
	
	public String patronMenu(){
		//String pMenu = "0) " + patrons.get(0) + '\n';
		String pMenu = "";
		for(int i = 0; i < patrons.size(); i++){
			pMenu = pMenu + i + ") " + patrons.get(i) + '\n';
		}
		
		return "List of Patrons\n\n" + pMenu + '\n';
	
	}
	/**
	* Returns the menu of the librarys publications
	*
	*@since 1.0
	*/
	
	@Override
	public String toString(){
		//String menu = "0) Book " + publications.get(0) + '\n';
		String menu = "";
		for(int i = 0; i < publications.size(); i++){
			if(publications.get(i) instanceof Video){
				menu = menu + i + ')' + publications.get(i).toStringBuilder(" Video "," runtime " + publications.get(i)) + '\n';}
			else if(publications.get(i) instanceof Publication){
				menu = menu + i + ')' + publications.get(i).toStringBuilder(" Book ","") + '\n';}
			}
		
		
		return name + '\n' + '\n' + menu;
	
	}
	
	private String name;
	private ArrayList <Publication> publications = new ArrayList<>();
	private ArrayList <Patron> patrons = new ArrayList<>();
}
