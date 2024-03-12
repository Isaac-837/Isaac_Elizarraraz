package library;
import java.time.Duration;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.FileReader;
import java.io.IOException;

/**
* Manages the publications that are videos
*
*@author Isaac Elizarraraz
*@version 1.0
*@since 1.0
*@license.agreement Gnu General Public License 3.0
*/
public class Video extends Publication{
/**
	* Creates a new video
	*
	*@param title  			The title of the video
	*@param author 			The author of the new video
	*@param copyright 		The year the new video was published
	*@since 1.0
	*/
		public Video(String title, String author, int copyright, int runtime){
		super(title,author,copyright);
		if(runtime <= 0){
			throw new InvalidRuntimeException(title,runtime);
		}
		this.runtime = this.runtime.ofMinutes(runtime);
}

public Video(BufferedReader br)throws IOException{
	super(br);
	String line = br.readLine();
	this.runtime = this.runtime.ofMinutes(Integer.parseInt(line));
	
}
@Override
public void save(BufferedWriter bw) throws IOException{
	super.save(bw);
	bw.write("" + runtime.toMinutes() + '\n');
	
}
/**
	* Returns the videos runtime in minutes
	*
	*@since 1.0
	*/
@Override
	public String toString(){
	
			return runtime.toMinutes() + " minutes";
			}
			 
private Duration runtime;

}
