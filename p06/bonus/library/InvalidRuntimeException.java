package library;

/**
* A custom error exception for invalid runtimes
*
*@author Isaac Elizarraraz
*@version 1.0
*@since 1.0
*@license.agreement Gnu General Public License 3.0
*/
public class InvalidRuntimeException extends java.lang.ArithmeticException{
	/**
	* Creates a new exception
	*
	*@since 1.0
	*/
	public InvalidRuntimeException(){
		super();
	
	}
	/**
	* Returns an error message
	*
	*@param message  		Chosen message
	*@since 1.0
	*/
	public InvalidRuntimeException(String message){
		super(message);
	
	}
	/**
	* Returns an error message including title and video
	*
	*@param title  			The title of the video
	*@param runtime 			Runtime of video
	*@since 1.0
	*/
	public InvalidRuntimeException(String title, int runtime){
		super(title + " has invalid runtime " + runtime);
	
	}







}
