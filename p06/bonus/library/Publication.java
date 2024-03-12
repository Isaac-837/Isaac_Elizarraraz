package library;
import java.time.LocalDate;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.FileReader;
import java.io.IOException;

/**
* Manages the publications
*
*@author Isaac Elizarraraz
*@version 1.0
*@since 1.0
*@license.agreement Gnu General Public License 3.0
*/

public class Publication{

	/**
	* Creates a new publication
	*
	*@param title  			The title of the publication
	*@param author 			The author of the new publication
	*@param copyright 		The year the new publication was published
	*@since 1.0
	*/

	public Publication(String title, String author, int copyright){
	if((copyright < 1900) || (copyright > 2023)){
			throw new IllegalArgumentException("Invalid copyright year");
	}
		this.title = title;
		this.author = author;
		this.copyright = copyright;
		
	}
	
	public Publication(BufferedReader br) throws IOException{
			String line = br.readLine();
			this.title = line;
			
			line = br.readLine();
			this.author = line;
			
			line = br.readLine();
			this.copyright = Integer.parseInt(line);
			
			line = br.readLine();
			if(line.equals("checked out")){
				line = br.readLine();
				this.loanedTo = new Patron(line,(line = br.readLine()));
				
				line = br.readLine();
				this.dueDate = LocalDate.parse(line);
			}
	}
	public void save(BufferedWriter bw) throws IOException{
			bw.write(title + '\n');
			bw.write(author + '\n');
			bw.write("" + copyright + '\n');
			if(loanedTo == null){
				bw.write("checked in" + '\n');		
			}
			else{
				bw.write("checked out" + '\n');
				loanedTo.save(bw);
				bw.write("" + dueDate.toString() + '\n');
			}
		
	}
	/**
	* Checks out a chosen publication
	*
	*@param patron  			The patron checking out
	*@since 1.0
	*/
	public void checkOut(Patron patron){
		if(loanedTo != null){
			System.out.println("That publication is currently checked out, please make another selection");
		}
		else{
			loanedTo = patron;
			dueDate = LocalDate.now();
			dueDate = dueDate.plusDays(14);
		}
	}
	/**
	* Checks in a publication that is currently checked out
	*
	*@since 1.1
	*/
	public void checkIn(){
		if(loanedTo == null){
			System.out.println("That publication has not been checked out yet");
		}
		else
			loanedTo = null;
	}
	/**
	* Creates a string for a publication, regardless of type
	*
	*@param pre  			The type of publication should be either book or video
	*@param mid  			The runtime
	*@since 1.0
	*/
	protected String toStringBuilder(String pre, String mid){
		if(loanedTo == null){
		return pre + '"' + title + '"' + ", by " + author + "(copyright " + copyright + ")" + 						mid;}
		else
		return pre + '"' + title + '"' + ", by " + author + "(copyright " + copyright + ")" + mid	+ "\n was loaned to " + loanedTo + " and is due on " + dueDate;
}
	/**
	* Creates a string for the book type of publication 
	*
	*@since 1.0
	*/
	@Override
	public String toString(){
		if(loanedTo == null){
			return '"' + title + '"' + ", by " + author + "(copyright " + copyright + ")";
			 
		}
		else
			return "The book " + '"' + title + '"' + ", by " + author + "(copyright " + copyright + ")"
			+ "\n was loaned to " + loanedTo + " and is due on " + dueDate;
		
	}
	private String title;
	private String author;
	private Patron loanedTo;
	private int copyright;
	private LocalDate dueDate;
}
