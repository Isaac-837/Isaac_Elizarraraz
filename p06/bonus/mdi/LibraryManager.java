package mdi;
import java.util.Scanner;
import library.Library;
import library.Patron;
import library.Publication;
import library.Video;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.FileReader;
import java.io.IOException;

public class LibraryManager {
	/**
	* Creates a space to manage a Library object
	*
	*@param library  			The Library that will be managed
	*@since 1.1
	*/
	
	public LibraryManager(Library library){
		int choice = -1;
		this.library = library;
	
		while(choice != 0){
			System.out.print(choiceMenu);
			choice = in.nextInt();
			in.nextLine();
			
			switch (choice){
			case 0:
				System.exit(0);
				break;
			case 1:
				System.out.println(library.toString());
				break;
			case 2:
				addPublication();
				break;
			case 3:
				addVideo();
				break;
			case 4:
				checkOut();
				break;
			case 5:
				checkIn();
				break;
			case 6:
				System.out.println(library.patronMenu());
				break;
			case 7:
				addPatron();
				break;
			case 8:
			try{
				open();
			}catch(Exception e){
				System.err.println("Failed to open: " + e);
			}
				break;
			case 9:
				try{
					save();
				}catch(Exception e){
					System.err.println("Failed to save: " + e);
				}
				break;
			
			default:
				if(choice != 0){
					System.out.println("Invalid option: " + choice);
				}
				break;		
			}
		}
	}
	public void save() throws IOException{
		System.out.print("Enter the file name: ");
		fileName = in.nextLine();
		
		try(BufferedWriter bw = new BufferedWriter(new FileWriter(fileName))){
			library.save(bw);
		}catch(Exception e){
			System.err.println("Failed to write: " + e);
		}
	}
	public void open() throws IOException{
		System.out.print("Enter the file name: ");
		fileName = in.nextLine();
		
		try(BufferedReader br = new BufferedReader(new FileReader(fileName))){
			library = new Library(br);
		}catch(Exception e){
			System.err.println("Failed to open: " + e);
		}
		
	}
	/**
	* Adds a publication to the Library
	*
	*@since 1.1
	*/
	public void addPublication(){
		String newName;
		String newAuthor;
		int newYear;
		
		System.out.print("Enter the name of the book: ");
		newName = in.nextLine();
		
		System.out.print("Enter the author of the book: ");
		newAuthor = in.nextLine();
		
		System.out.print("Enter the copyright date: ");
		newYear = in.nextInt();
		in.nextLine();
		
		Publication newPub = new Publication(newName,newAuthor,newYear);
		library.addPublication(newPub);	
	}
	/**
	* Adds video to the Library
	*
	*@since 1.1
	*/
	public void addVideo(){
		String newName;
		String newAuthor;
		int newYear;
		int newRuntime;
		
		System.out.print("Enter the name of the video: ");
		newName = in.nextLine();
		
		System.out.print("Enter author of the video: ");
		newAuthor = in.nextLine();
		
		System.out.print("Enter the copyright date: ");
		newYear = in.nextInt();
		in.nextLine();
		
		System.out.print("Enter the runtime: ");
		newRuntime = in.nextInt();
		in.nextLine();
		
		Video newVid = new Video(newName,newAuthor,newYear,newRuntime);
		library.addPublication(newVid);
		
	}
	/**
	* Checks out an existing publication
	*
	*@since 1.1
	*/
	public void checkOut(){
		System.out.println(library);
		System.out.print("Which publication do you want to check out? ");
		int pickBook = in.nextInt();
		System.out.println(library.patronMenu());
		System.out.print("Which Patron are you? ");
		int pickPatron = in.nextInt();
		library.checkOut(pickBook, pickPatron);
	}
	/**
	* Checks in a publication currently checked out
	*
	*@since 1.1
	*/
	public void checkIn(){
		System.out.println(library);
		System.out.print("Which publication are you returning: ");
		int pickPublication = in.nextInt();
		library.checkIn(pickPublication);
	
	}
	/**
	* Adds a patron to the Library
	*
	*@since 1.1
	*/
	public void addPatron(){
		String patronName;
		String newEmail;
		
		System.out.print("Enter your name: ");
		patronName = in.nextLine();
		
		System.out.print("Enter your email: ");
		newEmail = in.nextLine();
		
		Patron newPatron = new Patron(patronName,newEmail);
		library.addPatron(newPatron);
	}
	
	Scanner in = new Scanner(System.in);
	String choiceMenu = "=========\nMain Menu\n=========\n\nThe Library at Carpentersville IL\n\nPublications\n0) Exit\n1) List\n2) Add publication\n3) Add Video\n4) Check out\n5) Check in\n\nPatrons\n6) List\n7) Add\n\nFiles\n8) Open\n9) Save\n\nSelection: ";
	private Library library;
	private String fileName;
	public static void main(String[] args){
	
		try{
		Scanner in = new Scanner(System.in);
		
		Library library = new Library("The Library at Carpentersville IL");
		
		Publication book1 = new Publication("Harry Potter and the Prisoner of Azkaban",
		"J.K. Rowling", 1999);
		Publication book2 = new Publication("The Hunger Games", "Suzanne Collins", 2008);
		Publication book3 = new Publication("The Shinning", "Steven King", 1977);
		
		Patron person1 = new Patron("Isaac","student.uta.edu");
		Patron person2 = new Patron("Elizarraraz","Elizarraraz.uta.edu");
		Patron person3 = new Patron("Luke","Skywalker.uta.edu");
		
		Video tape1 = new Video("Spider-Man","Sam Raimi", 2002, 121);
		Video tape2 = new Video("Return of the Jedi","Richard Marquand and George Lucas", 1983, 131);
		Video tape3 = new Video("Alien","Ridley Scott", 1979, 117);
		
		library.addPublication(book1);
		library.addPublication(book2);
		library.addPublication(book3);
		
		library.addPublication(tape1);
		library.addPublication(tape2);
		library.addPublication(tape3);
		
		library.addPatron(person1);
		library.addPatron(person2);
		library.addPatron(person3);

		LibraryManager libraryManager = new LibraryManager(library);
		}
		catch(Exception e){
			System.err.println("Invalid Publication Input \n" + e);
		}
	}
}
