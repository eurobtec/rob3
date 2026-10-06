# TBPS

## 1. Introduction

The ROB3i's articulated arm has five axes and a gripper, all of which are powered by DC servo motors. The absolute position of all axes is determined by potentiometric rotary position transducers. The ROB3i's control system thus always knows the current position of all axes, even after a power failure.

The robot can be fitted with either an electrical or a pneumatic gripper, making it possible to perform an extremely wide range of different handling tasks. The integrated control system automatically identifies the gripper type and controls it accordingly.

For people who enjoy working with computers, the ROB3i is also fitted with an RS-232 serial interface, making it possible to control and program the robot from any IBM-compatible personal computer. The software package available for this purpose provides the programmer with extensive support: It is menu-operated, and all the control language instructions are permanently displayed on the screen for direct selection. To add an instruction to the control program you are writing, you simply select it with the cursor keys. This approach eliminates the possibility of syntax errors. Together with the comprehensive help texts which can be displayed as needed, all these features give the system an optimally simple user interface.

When the PC control software package is used, the ROB3i can be programmed both with the normal axis travel values and with Cartesian coordinates. The origin of the three-dimensional coordinate system is at the point of intersection of rotation axis 1 and the plane on which the robot is mounted. Traversing distances in the X, Y and Z planes are entered in millimeters.

In addition to standard PTP (point-to-point) control, the software package also supports linear interpolation. In this mode, the robot's gripper travels along a straight line between two taught points in space.

Programs can be delimited or subdivided with labels, which are "address markers" inserted in the program code. This feature makes it possible to chain individual program units stored in memory. Subprograms identified by labels can also be called in response to the results of polling the status of the system's eight digital inputs, making it possible for you to program the ROB3i to respond intelligently to external events. Eight digital outputs are also included, so that you can program the ROB3i to control its working environment. But that's not all. In addition, you can choose from five different travel speeds, set delays and repeating or endless loops, and much more.

For users who wish to develop their own robot control programs, software interfaces are available in the form of Include files in the languages BASIC, Pascal and C. These Include files contain subroutines for handling serial interface communication with the robot.

When IBM and Microsoft trademarks are mentioned in the text, this is understood to refer exclusively to the products of these companies. ROB is a registered trademark of P + P Elektronik GmbH, Nuremberg, West Germany.

## 2. Technical Specifications

Travel within the working range of each of the ROB3i's six axes is divided into 512 individual steps.

| Axis | Relative End Position | Angular Range |
| :--- | :--- | :--- |
| 1 Base rotation | right: POS 0 / left: POS 511 | 200 degrees |
| 2 Shoulder | up: POS 0 / down: POS 511 | 200 degrees |
| 3 Elbow | up: POS 0 / down: POS 511 | 200 degrees |
| 4 Wrist | up: POS 0 / down: POS 511 | 200 degrees |
| 5 Wrist roll | right: POS 0 / left: POS 511 | 400 degrees |
| *only for electric gripper* | | |
| 6 Gripper | open: POS 0 / closed: POS 100 | 60 mm |
| *only for pneumatic gripper* | | |
| 6 Gripper | open: POS 0 / closed: POS 1 | |

All axes can be moved simultaneously. The resolution of the axes makes it possible to access a total of $511^5$ points within the robot's reach. Gripper opening and closing also has a resolution of 511 steps.

In contrast to other robots, which always have a fixed home position, the ROB3i allows you to redefine the start position at the beginning of each program. This makes it possible to use the robot in the most difficult situations imaginable, for example when the home position is obstructed by an immovable object.

* **Resolution, steps per axis**: 512
* **Repeatability**: +/- 0,5 mm
* **Speeds**: 5
* **Maximum payload**: 500 g
* **Maximum traversing speed**: 750 mm per sec
* **Maximum continuous path speed**: 90 mm per sec
* **Drive**: DC servo motors
* **Feedback**: Absolute value transducers
* **Weight**: 13 kg
* **Ambient temperature**: 10 - 40 degrees C (50 - 104 F)
* **Interface**: RS-232
* **External power supply**: 24V DC at 8A, 9V DC at 3A
* **8 digital outputs**
* **8 digital inputs**

Programming options: With IBM-compatible personal computers (PC, XT, AT) and the TBPS software package; as a stand-alone unit together with the Teach Box; or with your own programs, written with the help of the Include files (controlling the robot from the computer via the RS-232 interface).

## 3. Dimensions and Axis Numbers

### Dimensions

* **Base footprint length**: 300
* **Base height**: 130
* **Height to axis A2**: 255 (130 + 115)
* **Arm length (between axes A2 and A3)**: 200
* **Forearm length (between axes A3 and A4)**: 200
* **Flange / gripper extension (after axis A4)**: 50
* **Link and base widths (top view)**: 220, 130, 110, 50, 100

### Axis Numbers and Rotation Angles

* **A1** = 200° (Base rotation)
* **A2** = 200° (Shoulder)
* **A3** = 200° (Elbow)
* **A4** = 200° (Wrist pitch)
* **A5** = 400° (Wrist roll / flange rotation)

Robot body markings: **P&P ROB 3i**

## 4. The PC Control Software Package

### 4.1 Introduction

The control software package is called TBPS, which stands for Teach Box Programming System. The purpose of TBPS is to provide you with all the programming options available with the ROB3i Teach Box in a modern, user-friendly PC environment. TBPS supports the entire ROB3i Teach Box instruction set. The instructions for communicating between the PC and the ROB3i are exactly the same as those used with the Teach Box.

The PC control software package allows you to control and program your ROB3i with any IBM PC, XT or AT, with or without an 8087 or 80287 math coprocessor. The coprocessor is not essential, but you will find that calculation of motion along linear paths will be very much faster if you have one. Here are a few examples of the time it can take to calculate a path through 256 points:

XT  4.77 MHz   without coprocessor  : 240 sec
XT  8.0  MHz   without coprocessor  : 140 sec
XT  4.77 MHz   with coprocessor     :  30 sec
XT  8.0  MHz   with coprocessor     :  10 sec
AT 12.0  MHz   without coprocessor  :  10 sec
AT 12.0  MHz   with coprocessor     :   7 sec

The above figures are only approximate values, of course. The actual times can vary very considerably, and will depend on your precise hardware configuration (by as much as 50% in some cases). The table is provided as a reference only, so that you don't mistakenly think that the program has crashed when complex calculations take a while to finish.

### 4.2 Program Files:

The TBPS software package is supplied on two 360 KB disks. Disk #1 contains the on-line version of the program, together with all the help files; disk #2 contains the off-line version and the Include files. The individual TBPS files are described below. You will find a description of the Include files in Section 9.

TBPS3i.EXE: On-line version of the control software. This is the main program, used to create ROB3i control programs using the "Teach-Box-oriented" programming language while actually operating the ROB3i.

TBPSOFF.EXE: Off-line version of the control software. Used for creating ROB3i programs with the ROB3i off line.

TBPS3i.EXE and TBPSOFF.EXE are both menu-operated. You can get help at any point by pressing F9 or F10.

TBINIT.EXE: Used for configuring the programming system. This program allows you to set the following parameters describing your system configuration:

- Drive where programs are to be stored    1 character   e.g. A,B,C
- Subdirectory on the drive               20 characters  e.g. \ROB3i
- Filename extension for control programs  3 characters   e.g. dat
- PC serial interface port no.            1 character   e.g. 1, 2

When you press the ESC key, TBINIT checks your entries and displays an error message if one of the parameters is incorrect. If you have made invalid entries, TBINIT will not allow you to exit the program by pressing the ESC key before you have corrected the errors. All the parameters you enter in TBINIT are stored in a configuration file called TB.CNF.

The TBKONV program (usage: TBKONV <source> <dest_ionation>) converts old Teach Box files into the new format which can be read by TBPS. This makes it possible to view all your Teach Box programs and edit them if necessary. Please enter the filenames for <source> and <destination> without an extension (maximum length 8 characters), as TBPS adds the .ACT extension automatically.

HELP files: All files with the .HLP extension are required by TBPS for displaying the help texts on the screen, and must be stored in the same drive and directory as the program files.

ROB3G.EXE/ROB3T.EXE: TBPS uses these files for displaying the ROB3i graphics on the screen. ROB3G.EXE is for systems with color monitors and color graphics adapters, and ROB3T.EXE is for monochrome monitors and Hercules-compatible graphics cards. TBPS loads the required program automatically as and when needed. Please DON'T try to run these two programs directly from the system prompt, as this can cause your computer to crash.

RS_ROB1.com/RS_ROB2.com: These programs handle the interrupt-controlled data exchange between the computer and the ROB3i via the COM1 or COM2 serial port. TBPS automatically calls the appropriate program for the port defined with TBINIT (see above).

MODE.COM or MODE.EXE: This is an MS-DOS system file required by TBPS. Please copy it onto your program disk or the TBPS subdirectory on your hard disk. Alternatively, you can add the directory where MODE.COM or MODE.EXE is stored in the PATH statement in your AUTOEXEC.BAT file in order to ensure that the TBPS can find it.

COMMAND.COM: Make sure that your computer's AUTOEXEC.BAT file contains the statement "SET COMSPEC = <drive>:\<path>\COMMAND.COM", where <drive> and <path> are the drive and directory where COMMAND.COM is stored on your hard disk. Add this statement to the file if necessary.

ANSI.SYS: Finally, your computer's CONFIG.SYS file should also contain the statement "DEVICE = <drive>:\<path>\ANSI.SYS", where <dirve> and <path> are the drive and directory where the system file ANSI.SYS is stored on your hard disk. Add the statement to the file if necessary. Please consult your MS-DOS manual if you are unsure about how to perform any of these installation tasks.

### 4.3 Installing on a Floppy Disk System

First, format either two 360 KB disks or (if you have a high-capacity drive) one 1.2 MB disk. Then copy all the files from the TBPS distribution disks to your freshly-formatted disks with the COPY *.* command. Refer to your MS-DOS manual for details if necessary. Store the original disks in a safe place, and never work with them directly, use them only for making your working copies!


### 4.4 Installing on a Hard Disk System

Before you begin, create a new subdirectory on your hard disk for the TBPS files. Then simply copy all the TBPS files onto your hard disk with the COPY *.* command. Refer to your MS-DOS manual if necessary. Store the original disks in a safe place, and use them only for copying the software onto your hard disk!


## 5. Hardware Requirements

The Teach Box Programming System runs on IBM-compatible personal computers of the PC, XT or AT class, with a minimum of 256 KB of RAM and MS-DOS 2.1 or higher. A standard Centronics parallel port is required for printer connection. All printers compatible with the Epson/IBM command set are supported. One RS-232 serial port is required for connecting the robot. For developing ROB3i control programs you will need at least one 360 KB floppy disk drive.

## 6. Hardware Installation and Starting the Program

[Diagram showing connections to the robot unit]
- RESET button
- I/O PORT
- RS 232 <-- PC
- Power supply <-- 24V/6A, 9V/3A

## 7. Using the TBPS Package

### 7.1. The TBPS Program Modules

Two different versions of the TBPS program are supplied on the distribution disks:

**Version 1: On-line Version**
This version is copy-protected with the system number check described above. Each ROB3i unit has a different serial number, which is recorded in the software supplied with the unit. It is thus not possible to run the on-line version without connecting your ROB3i, or with a ROB3i with a different serial number. The ROB3i unit must remain connected to your PC throughout your programming session, otherwise the program will be aborted.

**Version 2: Off-line Version**
This is the "slimline" version of the TBPS package, which is designed for developing the draft versions of your programs. You can't control the ROB3i with the off-line version, but you can load, store, write and print ROB3i control programs. The differences between TBPS and TBPSOFF functions and options are described in the explanations which follow.

### 7.2. The Main Menu

Following successful completion of the system checks, the Main Menu appears on the screen. You can choose from a total of seven menu options (five options in TBPSOFF).

* **Load Program** : F1
* **Save Program** : F2
* **Create Program** : F3
* **Run Program** : F4 (not available in TBPSOFF)
* **Teach Box Communication** : F5 (not available in TBPSOFF)
* **Print Program Listing** : F6
* **Exit** : F7

There are a number of different ways of selecting the menu options:

* **With the function keys**:
  Simply press the function key shown to the right of the desired option.
* **With the cursor keys (up/down)**:
  The selected menu option is highlighted; select by pressing ENTER (CR on some keyboards).

The following additional options are available at any point in the program, independent of the Main Menu options. These options are only available via the function keys, however.

* **ROB3i Graphic** : F8 displays a graphic representation of the ROB3i, with the axis designations.
* **Module** : F9 displays a help window at the top of the screen with a description of the selected program module. You can scroll through the help text with the cursor keys. ESC closes the help window.
* **Help** : F10 displays a description of all the options available in the current program module. You can scroll through the text with the cursor keys in the same way as with Module : F9.

You can abort any selected option by pressing ESC twice.

### 7.3. Load Program : F1

When you select the Load Program module, the system first displays a list of all the files with the extension which you have stored in your TB.CNF configuration file with TBINIT. The program summary of the highlighted program file is also displayed (Filename, Author, Description, Creation Date). If there are more program files than can be displayed on the screen, you can scroll through the list with the cursor up and cursor down keys.

To load a program, first move the highlight to the desired program name with the cursor keys and then press ENTER (CR on some keyboards) or F1.

You can enter the filename manually by pressing F2. The name can be up to eight characters long. If you enter a new filename, you can also use this function to clear the current program from the memory so that you can write a new one. The filename extension defined in TB.CNF is added automatically.

Pressing F9 (Module) displays a help window with a detailed description of this program module.
Pressing F10 (Help) displays a help window containing descriptions of all available functions.
Pressing ESC twice returns you to the main menu.

### 7.4. Save Program : F2

This module can only be activated when you have loaded a program into memory, or while a program you have just created is still in the memory. When you select this program module, a list of all the files with the extension set in TB.CNF is displayed on the screen. The program summary of the highlighted program file is also displayed (Filename, Author, Description, Creation Date). If there are more program files than can be displayed on the screen, you can scroll through the list with the cursor up and cursor down keys.

Pressing either ENTER (CR) or F1 saves the current program in the highlighted file. This makes it easy to save programs which you are developing in a step-by-step process in the same file every time. If you have already tested the program with the Run Program module, all the values of any calculated LINE movements are stored in the file automatically, thus avoiding long calculation times the next time you run the program.

To save the program in a new file, press F2. The filename you enter can be up to eight characters long. The extension defined in TB.CNF is added automatically. You can also enter the name of the program author and a program description. Pressing ENTER or F1 stores the file together with the entered parameters.

Pressing F9 (Module) displays a help window with a detailed description of this program module.
Pressing F10 (Help) displays a help window containing descriptions of all available functions.
Pressing ESC twice returns you to the main menu.

### 7.5. Create Program : F3

This program module is used for writing new ROB3i control programs using the Teach Box instructions. When you select the module, three independent, permanent windows are displayed, together with a menu bar at the bottom of the screen.

#### 7.5.1. The Listing Window

The Listing Window displays the program listing, comprising the sequence of commands and instructions which make up the ROB3i control program which you are editing. If you have loaded a program file before activating this module, the program listing will be displayed in the window. If you have "loaded" a nonexistent file by entering a new filename, the window will be empty, with MAR 0 in the first line to mark the beginning of your new program.

You can only access the Listing Window indirectly, via the Instruction Window. You cannot edit the text displayed in the Listing Window. When you are writing programs normally, a highlighted line below the last line of the listing shows that the system is ready for inputs at this point.

When you activate the Listing Window from the Instruction Window, the following keys are available for scrolling through the program:

* **Cursor Up**: Up one line
* **Cursor Down**: Down one line
* **PGUP**: Page up
* **PGDN**: Page down
* **HOME**: Go to top of program
* **END**: Go to bottom of program

No character keys are enabled.

There are two different editing modes for entering instructions via the Instruction Window, Insert and Overwrite. These modes are selected with the INS and DEL keys.

* **Insert (INS)**: In Insert mode, new program lines are inserted above the current cursor position, and all the following lines are moved down by one line.
* **Overwrite (DEL)**: In Overwrite mode, the program line at the cursor position is overwritten by the new program line.

#### 7.5.2. The Instruction Window

The Instruction Window displays a list of all the instructions and commands needed to write ROB3i control programs. The window also gives you access to useful help functions to make writing programs faster and easier. To select instructions, simply move the highlight to the desired instruction with the cursor keys and then press ENTER.

The following instructions are displayed in the window:

| | |
| --- | --- |
| MARK | COMMENT |
| TIMER | END |
| POS Axis | HALT |
| POS x,y,z | DEL |
| GOTO | INS |
| OUT | SEARCH |
| IF | |

You can move the highlight around in the list with the following keys:

* **Cursor Up**: Up one line
* **Cursor Down**: Down one line
* **PGUP**: Page up
* **PGDN**: Page down
* **HOME**: Go to top of instruction list
* **END**: Go to bottom of instruction list

No character keys are enabled.

#### 7.5.3. The Message Window

In Message Window brief messages are displayed explaining the currently selected option. When you select instructions in the Instruction Window, a concise description of the selected instruction together with its parameter value range is displayed in the Message Window. If the selected instruction requires that you input parameters, a message is displayed explaining the type of parameter expected.

#### 7.5.4. The Input Window

This window only appears when you have to enter parameters for the selected instruction. The system checks that the entered values are within the range permitted for the instruction. Confirm your inputs with ENTER. You can abort input by pressing ESC.

#### 7.5.5. The Instructions

The following instructions and commands are available in the Instruction Window for use in your ROB3i control programs:

##### MARK:
This instruction (= MAR) is used for setting labels in your program. You can use these labels for both unconditional (GOTO) and conditional (IF) jumps and loops. TBPS will not allow you to enter a new label with a number that has already been assigned.

* **Format**: Label no.
* **Value range**: 0 <= m <= 118
* **Input**: numeric

**Example**: MAR 100 : Set label no. 100

##### TIMER:
This instruction is used to set defined delays. You must enter a numeric parameter for the delay period. 1 = 100 ms, 5 = 500 ms, etc.

* **Format**: Delay value
* **Value range**: 1 <= t <= 65535 (= 109 min)
* **Input**: numeric

**Example**: TIM 10 : 1 second delay

##### POS Axis:
In the TBPSOFF version of the program, selecting this instruction generates a pseudo POS Axis instruction in the listing. This can then be converted to a genuine positioning instruction with the TBPS version. When you select POS Axis in TBPS, a new screen is displayed in which you can set the robot's axes directly using teach movements. The screen contains a listing window showing the last four lines of the program, a window showing the axis positions, and a selection window for selecting axes, speed and movement type. The following graphics aids are also provided:

* **F8**: Displays a graphic representation of the robot with axis designations.
* **F7**: Displays the positions of the axes in an axis diagram.

To position an axis, select the Select Axis command and enter the number of the desired axis. You can then move the axis with the cursor keys. When the axis is positioned correctly, you can terminate the sequence by pressing ESC twice.

The cursor key assignments for the various axes are as follows:

* **Cursor right**: 1 bit | Position right | (axes 1, 5 and 6)
* **Cursor left**: 1 bit | Position left | (axes 1, 5 and 6)
* **Cursor up**: 1 bit | Position up | (axes 2, 3 and 4)
* **Cursor down**: 1 bit | Position down | (axes 2, 3 and 4)
* **Home**: 10 bits | Position left | (axes 1, 5 and 6)
* **END**: 10 bits | Position right | (axes 1, 5 and 6)
* **PGUP**: 10 bits | Position up | (axes 2, 3 and 4)
* **PGDN**: 10 bits | Position down | (axes 2, 3 and 4)

No character keys are enabled.

The Speed command allocates one of five possible speeds to all the axes participating in the movement, with 1 representing the lowest speed and 5 the highest. This command is optional — if you don't select it, the system will default to a speed of 5 for all axes. This feature makes programming faster, as you don't need to enter a speed for every single movement.

After selecting the speed, you can then select the Movement Type command to specify either Point-to-Point (PTP : P) or LINE (LIN : L) movement. When a LINE movement is executed, the gripper tip is moved along a straight line from the previous position to the defined target position; the relative gripper angle is adjusted continuously to maintain the new angle as it travels along the defined path. This means that you can maintain a stable gripper attitude during the movement by setting the same gripper position for the beginning and the end of the movement.

Pressing ESC twice adds the instruction to the program. Pressing ESC twice again returns you to the editing screen.

Format:
POS 1:100,5P (instruction to move axis 1 to position 100, at speed 5 and with a PTP movement).

POS 1:123,2:14,3:144,4:200,5:0,6:100,5L (instruction moving all axes to the positions specified after the colons, at speed 5 and with a LINE movement).

##### POS x,y,z:

Selecting this instruction in the TBPSOFF version of the program generates a pseudo POS x,y,z instruction in the listing. This can then be converted to a genuine positioning instruction with the TBPS version. When you select POS Axis in TBPS, a new screen is displayed in which you can set the robot's axes directly by entering coordinate values. The screen contains a listing window showing the last four lines of the program, a window showing the current coordinate values, and a selection window for selecting coordinates, speed and movement type. The following graphics aids are also provided:

* **F8**: Displays a graphic representation of the robot with axis designations.
* **F7**: Displays the positions of the axes in an axis diagram.

The POS x,y,z instruction allows you to position the robot's axes by entering Cartesian coordinates. TBPS performs a plausibility check in order to make sure that the arm can actually move to the entered position. The origin of the three-dimensional coordinate system is at the point of intersection between rotation axis 1 and the plane on which the robot is mounted. The x, y and z coordinates are entered in millimeters.

The Speed and Movement Type commands function in the same way as with the POS Axis instruction.

Pressing ESC twice adds the instruction to the program. Pressing ESC twice again returns you to the editing screen.

Format:
POS X:200,Y:50,Z:40,5P (positions the robot's axes so that the gripper tip is moved to the point in space defined by the coordinates 200, 50 and 40, with a PTP movement and at speed 5).

POS X:200,Y:50,Z:40,5L (positions the robot's axes so that the gripper tip is moved to the point in space defined by the coordinates 200, 50 and 40, with a LINE movement and at speed 5).

##### GOTO:
This instruction (= GTO) is used for executing unconditional jumps to labels (see MARK above). You can also repeat a movement sequence a specific number of times by entering a loop control variable.

* **Format**: Label no.
  * **Value range**: 0 <= m <= 118
  * **Input**: numeric
* **Format**: Loop repetitions
  * **Value range**: 0 <= x <= 255
  * **Input**: numeric

**Examples**:
* `GTO 10` : Unconditional loop to label 10.
* `GTO 20 . 5` : Loop to label 20 five times.

##### OUT:
This command is used to set or clear any of the eight digital outputs. The outputs are active low.

* **Format**: Output no.
  * **Value range**: 1 <= o <= 8
  * **Input**: numeric
* **Format**: Set/Clear
  * **Value range**: +, - ('+' = set, '-' = clear)
  * **Input**: alphanumeric

**Example**: `OUT 7 +` : Set output 7 to low.

##### IF:
This command is used to poll the status of any of the eight digital inputs in order to control program flow. Low is evaluated as logical TRUE. All the inputs are active low.

* **Format**: Input no.
  * **Value range**: 1 <= i <= 8
  * **Input**: numeric
* **Format**: Label no.
  * **Value range**: 1 <= m <= 118
  * **Input**: numeric

**Examples**:
* `IF 7` : Wait until input 7 is low.
* `IF 3 . 10` : If input 3 is low go to label 10, else continue normal program execution

##### COMMENT:
This instruction (= COM) allows you to enter comments in the current line of the program.

* **Format**: Comment text
  * **Max. characters**: 20
  * **Input**: alphanumeric

**Example**: `COM Light on?` : Commentary line with text "Light on?"

##### HALT:
This instruction is used as a separator between two sequential programs in the memory. Program execution is halted when this instruction is processed. To call a program coming after the HALT instruction, you must place a label in the called program's first line and execute a jump to the label before HALT is executed.

##### END:
This instruction terminates the program. You cannot exit the program editor until you have inserted the END instruction (= INS.) in your program.

##### DEL:
Deletes a program line. After selecting the instruction you can then select the line to be deleted with the cursor up and down keys, then press ENTER to delete. Depending on the current editing mode (Overwrite or Insert), the next instructions you enter will then either overwrite the following lines, or be inserted in the listing, shifting the following lines downwards. The instruction is not displayed in the Listing Window. If you try to delete a line containing a label with DEL, the system will first check to make sure that the program does not contain any jump instructions with the selected label as their destination. If it does, the line will not be deleted, and a message will be displayed. You can also position the cursor at any line in the program with Line Edit F1 and the cursor up and down keys.

##### INS:
Inserts a line in the program you are editing, above the current cursor position. Here too, you can first position the cursor with Line Edit F1 and the cursor up and down keys. After selecting this instruction and pressing RETURN, all the following lines are shifted down by one line, irrespective of the current editing mode, and an empty line is inserted. If you are in Insert mode the next instructions you enter will then either overwrite the following lines, if you are in Overwrite they will be inserted in the listing, shifting the following lines downwards. The instruction is not displayed in the Listing Window.

##### SEARCH:
Searches for a text string or a program line. When you have entered your search string, the search is performed starting at the current cursor position, and continues until the string is found or the end of the listing is reached without finding the string. To repeat the search, you must select SEARCH again. Pressing ESC aborts the search.

* **Format**: Search string
  * **Characters**: 20
  * **Input**: alphanumeric, upper case

### 7.6 Run Program : F4

This function allows you to test your freshly-created program directly by running it on the ROB3i. After you select the function, TBPS first runs an analysis program which calculates the labels and the input and output channels, generating important parameters for the ROB3i control sequence. Once this has been done, a submenu is displayed, allowing you to choose from a number of different run options (see below).

When you select one of the submenu options, TBPS first locates all the LINE movements in the program and calculates the individual points for their paths. Depending on the model of computer you are using, these calculations can take anywhere from a few seconds to a number of minutes. The calculated values are stored with the program when you save it, which means that they only need to be calculated once, thus avoiding time-consuming calculations the next time you load and run the program.

#### 7.6.1 RUN: Normal Run without Restrictions

To start the program, simply press the space bar. Program execution will only be terminated under the following circumstances:

* When an INS. (END) or DEL. (HALT) instruction is encountered. When one of these instructions is processed, the robot stops in the last position it was moved to, and a message is displayed informing you that an END or HALT instruction has been executed. The program is then reset internally. If you wish, you can run the program again by pressing the space bar once more.
* When you press the space bar during execution. ROB3i will then complete execution of the current instruction (delay, movement etc.), after which program execution will be terminated. Pressing the space bar again resumes execution with the next line.

#### 7.6.2 RUN: From Label

This option lets you start execution at any of the labels you have set in the program. You will be prompted to enter the label number. If you confirm without entering a value, the system will default to label no. 0 (i.e. the beginning of the program).

If you enter a label number, the system first checks that a label with that number has been set in the program. If the number is found, you can then start execution from that point. If not, an error message will be displayed.

#### 7.6.3 RUN: Single-Step Mode

This option allows you to run your program one instruction at a time. The program is displayed on the screen, and the instruction being executed is highlighted. Pressing the space bar steps through the program. A second window is displayed next to the listing window, showing the current status of the I/O channels used by the program and the positions of axes 1 6.

#### 7.6.4 RUN: Single-Step Mode, from Label

This option allows you to run your program in single-step mode, starting at a specified label. See 7.6.3 and 7.6.2 above for details on stepping through the program and entering the label number.

#### 7.6.5 RUN: Automatic Single-Step Mode

When you select this option, TBPS runs the program normally, but inserts a delay of approx. one second between the execution of one instruction and the next. Pressing the space bar interrupts execution, pressing it again resumes.

#### 7.6.6 RUN: Automatic Single-Step Mode, from Label

This option selects the automatic single-step mode, starting at a specified label. See 7.6.5 and 7.6.2 above for details on program execution and entering the label number.

### 7.7. TEACHBOX Communication : F5

Selecting the Teach Box Communication module displays a submenu with four options on the screen. This module is the link between the PC software package and the Teach Box programming unit. It allows you to download complete control programs into the robot's memory and start them with the Teach Box, and to upload and edit programs created with the Teach Box. The system returns you to the Main Menu after the completion of each operation.

#### 7.7.1. Download Teach Box File to ROB3i : F1

Loads a Teach Box file from disk and then downloads it into the ROB3i's memory. Teach Box files are program files created with the Teach Box and the ROB3i and then stored on a floppy or hard disk (extension .ACT). TBPS uses the Load Program module for filename entry (see Section 7.3).

#### 7.7.2. Upload Teach Box Program from ROB3i : F2

Uploads the program currently in the ROB3i's memory to the PC and stores it in a file on a floppy or hard disk. TBPS uses the Save Program module for filename entry (see Section 7.4). You cannot edit the program with this function.

#### 7.7.3. Download Program File to ROB3i : F3

Downloads a compiled control program file from the PC to the Teach Box, transferring all the commands into the robot's memory in the form of an executable program. The ROB3i can then be operated without the PC whenever necessary, as the program can be started directly from the Teach Box. The program can also be uploaded back into the PC, if desired.

#### 7.7.4. Upload Program File from ROB3i : F4

Uploads the program currently in the ROB3i's memory to the PC and converts it into a file which can be edited with TBPS.

### 7.8. Print Program listing : F6

Used for generating printouts of your program listings. When you select PRINT, TBPS will first prompt you to enter the numbers of the first and last lines which you want to print. If you confirm these prompts without making any entries, the entire listing will be printed.

Next, you will be prompted to enter a brief description of your program and the name of the program author. These data records are the same as those recorded with the Load Program and Save Program functions.

Each page of the printout comprises 65 lines, and begins with a header containing the program description, the author's name, the creation date and time and the page number. All lines are printed with line numbers. In the event of printer malfunctions or other problems, the function is aborted and an appropriate error message is printed out.

### 7.9. Exit : F7

Exits TBPS and returns you to DOS. Please note that this clears any program you have been editing from the computer's memory. You should thus always remember to save your program in a file before exiting TBPS or TBPSOFF, otherwise all your editing changes will be lost for good!
