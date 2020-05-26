#! /usr/bin/env python3

# Authors:
# Daniel Mallia
# Andrew Hrabovcak
# Vishnu Rampersaud
# Jordan Sze
# Ralph Vente
# Date Begun: 9/13/2019

# To Do:
# Write all commented out functions
# Include ability to ignore source code comments - time permitting
# Time permitting, this can all be converted into a "compiler" class with
# the current globals as members but functionally it is the same concept
# open issues:
# translate arithmetic (maybe translate_body) are not called for every function

# Reminders:
# Include checks for out of array bounds - this is why length was stored
# Write check for empty function
# Write additional checks for improper source code - time permitting

# Imports
import sys
import string

try:
    from icecream import ic
    ic.disable()
except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa
# Globals:
out = None # output file
source_Code = [] # list of source code lines
pc = 0 # program counter
rsp = 0 # simulated rsp
function_Names = [] # list of function names
frame_Vars = {} # Lookup dict of arguments and locals
                # frame_Vars[name] = (address, value, array(boolean), array_Length, array_Vals)
arg_Queue = [] # Queue for ordering arg processing
local_Queue = [] # Queue for ordering local processing
l_Count = 0 # Counter for assembly block numbering
output_Line_Number = 1 # Counter for assembly output line numbering
for_loop_counter = 0
for_limit = 0
for_nested = False
number_of_nested_for = 0

#---------------------------------------------------------
#Array global variables
arr_call = "arr_call"
rlocal = "rlocal"
wlocal = "wlocal"
rfunction = "rfunction"
wfunction = "wfunction"
#---------------------------------------------------------

# Write utility
# @text - string to write to output file
# Writes string with current line number in front to file
def write(text):
    global output_Line_Number
    output = str(output_Line_Number) + ". "
    if(output_Line_Number < 10):
        output = output + '\t'
    output = output + text + '\n'
    out.write(output)
    output_Line_Number +=1

# Array utility
# @text - name of variable to check if is an array
# Returns True if brackets declaring size are found; else False
def is_Array(text):
    if(text.find('[') != -1):
        return True
    else:
        return False

# Reset global variables (after a function translation)
def reset_Globals():
    global rsp, frame_Vars, arg_Queue, local_Queue, for_loop_counter, for_limit
    rsp = 0
    frame_Vars = {}
    arg_Queue = []
    local_Queue = []
    for_loop_counter = 0
    for_limit = 0
    for_nested = False
    number_of_nested_for = 0

# Parser for function prototype
# Updates function_Names, frame_Vars, arg_Queue and rsp in accordance
# with prototype.
def parse_Func_Head():
    global function_Names, frame_Vars, arg_Queue, rsp
    head = source_Code[pc]
    reg_Args = []
    push_Args = []

    _, _, remaining = head.partition(' ')
    function_Name, _, remaining = remaining.partition('(')
    function_Names.append(function_Name)
    remaining = (remaining.rstrip('){')).split()

    # Split argument list if more than 6 arguments (12 is for type, arg pairs -
    # ex: 'int', 'b')
    if(len(remaining) > 12):
        reg_Args = remaining[:12]
        push_Args = remaining[12:]
    else:
        reg_Args = remaining[:]

    # Process arguments passed by register
    while(len(reg_Args) >= 2):
        type = reg_Args.pop(0)
        name = reg_Args.pop(0).rstrip(',)')
        value = -1
        array_Vals = []
        array = is_Array(name)
        if(array):
            rsp -= 8
            address = rsp
            array_Length = int(name[-2])
            name = name[:-3]
        else:
            rsp -= 4
            address = rsp
            array_Length = 0
        frame_Vars[name] = (address, value, array, array_Length, array_Vals)
        arg_Queue.append(name)

    # Process arguments passed by stack
    push_Address = 16
    while(len(push_Args) >= 2):
        type = push_Args.pop(0)
        name = push_Args.pop(0).rstrip(',)')
        value = -1
        array = is_Array(name)
        array_Vals = []
        address = push_Address
        if(array):
            array_Length = int(name[-2])
            name = name[:-3]
        else:
            array_Length = 0
        frame_Vars[name] = (address, value, array, array_Length, array_Vals)

# Search for local variables
# Updates frame_Vars, local_Queue, rsp accordingly
def check_Local_Decs():
    global frame_Vars, local_Queue, rsp
    temp = pc
    block_Counter = 1
    while(temp < len(source_Code) and block_Counter > 0):
        curr_Instr = source_Code[temp]

        # Use brackets to detect end of function
        if(curr_Instr.find('{') != -1):
            block_Counter +=1

        if(curr_Instr.find('}') != -1):
            block_Counter -=1

        # Find declarations by looking for "int"
        if(curr_Instr.find('int') != -1):
            begin_Dec = curr_Instr[(curr_Instr.find('int')):]
            dec = begin_Dec.split()
            name = dec[1].rstrip(";")
            value = -1
            array_Vals = []
            array = is_Array(name)
            if(array):
                array_Length = int(name[-2])
                rsp -= 4
                address = rsp
                rsp -= 4*(array_Length-1)
                name = name[:-3]
                for i in range(array_Length):
                    array_Vals.append(int((dec[3+i].lstrip('{')).rstrip(',};')))
            else:
                rsp -= 4
                address = rsp
                array_Length = 0
                ic(dec)
                if "for" in curr_Instr: 
                    value = dec[3].rstrip(";")
                else: 
                    value = dec[-1].rstrip(";")
            if(name in frame_Vars):
                print('Compile error: name conflict with variable ', name)
                sys.exit()
            frame_Vars[name] = (address, value, array, array_Length, array_Vals)
            local_Queue.append(name)
        temp +=1

# Write function prologue in assembly to file
def write_Func_Prologue():
    global arg_Queue, local_Queue
    registers_64 = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
    registers_32 = ['edi', 'esi', 'edx', 'ecx', 'r8d', 'r9d']

    # Standard beginning
    write('\tpush\trbp')
    write('\tmov\t\trbp, rsp')
    write('\tsub\t\trsp, ' + str(rsp))

    # Write argument pushes to stack
    index = 0
    while(len(arg_Queue) > 0):
        name = arg_Queue.pop(0)
        address = frame_Vars[name][0]
        if(frame_Vars[name][2] == True):
            register = registers_64[index]
            write('\tmov\t\tQWORD PTR [rbp' + str(address) + '], ' + register + '\t; ' + name)
        else:
            register = registers_32[index]
            write('\tmov\t\tDWORD PTR [rbp' + str(address) + '], ' + register \
            + '\t; ' + name)
        index +=1

    # Write local variable assignments
    while(len(local_Queue) > 0):
        name = local_Queue.pop(0)
        address = frame_Vars[name][0]
        value = frame_Vars[name][1]
        offset = 0
        # If array, must allocate all values
        if(frame_Vars[name][2] == True):
            for val in frame_Vars[name][4]:
                write('\tmov\t\tDWORD PTR [rbp' + str(address - 4 * offset) \
                    + '], ' + str(val) + '\t; ' + name + '[' + str(offset) + ']')
                offset += 1
        else:
            write('\tmov\t\tDWORD PTR [rbp' + str(address) + '], ' + str(value) + '\t; ' + name)


# Function for looping through body of any combination statement -
# conditionals, loops, functions - calling appropriate translations
def translate_Body():
    global pc
    current_pc = pc
    ic()
    lengthsource = len(source_Code)
    while(pc < lengthsource):
        ic(pc, source_Code[pc])
        if ((len(source_Code[pc]) == 1) and ("{" in source_Code[pc])):
            pc+=1
        elif "for" in source_Code[pc]:
            translate_For()
        elif "if" in source_Code[pc]:
            translate_Conditional()
        elif "+" in source_Code[pc]:
            translate_Arithmetic("+")
        elif "-" in source_Code[pc]:
            translate_Arithmetic("-")
        elif "return" in source_Code[pc]:
            translate_Return()
        elif "}" in source_Code[pc]:
            pc += 1
            return
        elif "int" in source_Code[pc]: 
            pc += 1
        else:
            lengthlist = len(function_Names)
            for i in range(lengthlist):
                nameoffunction = function_Names[i]
                if nameoffunction in source_Code[pc]:
                    translate_Function_Call()

        end_pc = pc
        if (current_pc == end_pc): 
            print ("pc was not incremented properly. Stuck at pc = ", pc)
            sys.exit()



def translate_Arithmetic(optype):
    global pc
    ic(frame_Vars)
    statements = source_Code[pc][:-1].strip().split("=")
    lhs = statements[0].strip()
    rhs = statements[1].strip()
    operands = rhs.split(optype)
    ic(lhs, rhs, operands)
    ic(frame_Vars[lhs])
    command = {"+":"add", "-":"sub"}[optype]
    stripped_operands = [operand.strip() for operand in operands]
    ic(stripped_operands)
    stck_offsts = [getOffset(op) for op in stripped_operands]

    print(stripped_operands)
    if not stripped_operands[0].isdigit():
        toWrite = frame_Vars[stck_offsts[0]][0]
    else:
        toWrite = operands[0]
    # inital move to set up addtion
    write("\tmov \teax, {} \t; {}".format(toWrite, operands[0]))

    for stck_offst, operand in zip(stck_offsts[1:], stripped_operands[1:]):
        print(operand)
        if not operand.isdigit():
            toWrite = frame_Vars[stck_offst][0]
            write("\t{} \teax, \tDWORD PTR [rbp{}] \t; {}".format(command, toWrite, operand))
        else:
            toWrite = stck_offst
            write("\tmov \teax, {} \t; {}".format(operand, operand))
    write("\tmov \tDWORD PTR [rbp{}], eax\t; {}".format(frame_Vars[lhs][0], lhs))
    pc+=1

def translate_Conditional():
    global pc
    global l_Count
    inner = source_Code[pc].split("(")
    condition = inner[1]
    l_Count += 1
    if ">=" in condition:
        innersplit = condition.split(">=")
        lhs = innersplit[0]
        lhs = lhs.strip()
        rhs1 = innersplit[1]
        rhssplit = rhs1.split(")")
        rhs2 = rhssplit[0]
        rhs2 = rhssplit[0].strip()
        if "[" in lhs:
            arraysplit = lhs.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
        elif lhs.isnumeric() == False:
            laddress = frame_Vars[lhs][0]
            write('\tmov\t\teax,\tDWORD PTR [rbp' + str(laddress) + ']')
        else:
            raddress = frame_Vars[rhs2][0]
            write('\tmov\t\teax,\t' + lhs)
        if "[" in rhs2:
            write('\tmov\t\tedx,\teax')
            arraysplit = rhs2.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
            write('\tcmp\t\tedx,\teax')
        elif rhs2.isnumeric() == False:
            write('\tcmp\t\teax,\tDWORD PTR [rbp' + str(raddress) + ']')
        else:
            write('\tcmp\t\teax,\t' + rhs2)
        write('\tjl\t\tIF' + str(l_Count))
    elif "<=" in condition:
        innersplit = condition.split("<=")
        lhs = innersplit[0].strip()
        rhs1 = innersplit[1]
        rhssplit = rhs1.split(")")
        rhssplit = rhssplit[0].strip()
        if "[" in lhs:
            arraysplit = lhs.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
        elif lhs.isnumeric() == False:
            laddress = frame_Vars[lhs][0]
            write('\tmov\t\teax,\tDWORD PTR [rbp' + str(laddress) + ']')
        else:
            write('\tmov\t\teax,\t' + lhs)
        if "[" in rhssplit:
            write('\tmov\t\tedx,\teax')
            arraysplit = rhs2.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
            write('\tcmp\t\tedx,\teax')
        elif rhssplit.isnumeric() == False:
            raddress = frame_Vars[rhs2][0]
            write('\tcmp\t\teax,\tDWORD PTR [rbp' + str(raddress) + ']')
        else:
            write('\tcmp\t\teax,\t' + rhssplit)
        write('\tjg\t\tIF' + str(l_Count))
    elif ">" in condition:
        innersplit = condition.split(">")
        lhs = innersplit[0]
        lhs = lhs.strip()
        rhs1 = innersplit[1]
        rhssplit = rhs1.split(")")
        rhs2 = rhssplit[0]
        rhs2 = rhssplit[0].strip()
        if "[" in lhs:
            arraysplit = lhs.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
        elif lhs.isnumeric() == False:
            laddress = frame_Vars[lhs][0]
            write('\tmov\t\teax,\tDWORD PTR [rbp' + str(laddress) + ']')
        else:
            write('\tmov\t\teax,\t' + lhs)
        if "[" in rhs2:
            write('\tmov\t\tedx,\teax')
            arraysplit = rhs2.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
            write('\tcmp\t\tedx,\teax')
        elif rhs2.isnumeric() == False:
            raddress = frame_Vars[rhs2][0]
            write('\tcmp\t\teax,\tDWORD PTR [rbp' + str(raddress) + ']')
        else:
            write('\tcmp\t\teax,\t' + rhs2)
        write('\tjle\t\tIF' + str(l_Count))
    elif "<" in condition:
        innersplit = condition.split("<")
        lhs = innersplit[0]
        lhs = lhs.strip()
        rhs1 = innersplit[1]
        rhssplit = rhs1.split(")")
        rhs2 = rhssplit[0]
        rhs2 = rhssplit[0].strip()
        if "[" in lhs:
            arraysplit = lhs.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
        elif lhs.isnumeric() == False:
            laddress = frame_Vars[lhs][0]
            write('\tmov\t\teax,\tDWORD PTR [rbp' + str(laddress) + ']')
        else:
            write('\tmov\t\teax,\t' + lhs)
        if "[" in rhs2:
            write('\tmov\t\tedx,\teax')
            arraysplit = rhs2.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
            write('\tcmp\t\tedx,\teax')
        elif rhs2.isnumeric() == False:
            raddress = frame_Vars[rhs2][0]
            write('\tcmp\t\teax,\tDWORD PTR [rbp' + str(raddress) + ']')
        else:
            write('\tcmp\t\teax,\t' + rhs2)
        write('\tjge\t\tIF' + str(l_Count))
    elif "==" in condition:
        innersplit = condition.split("==")
        lhs = innersplit[0]
        lhs = lhs.strip()
        rhs1 = innersplit[1]
        rhssplit = rhs1.split(")")
        rhs2 = rhssplit[0]
        rhs2 = rhssplit[0].strip()
        if "[" in lhs:
            arraysplit = lhs.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
        elif lhs.isnumeric() == False:
            laddress = frame_Vars[lhs][0]
            write('\tmov\t\teax,\tDWORD PTR [rbp' + str(laddress) + ']')
        else:
            write('\tmov\t\teax,\t' + lhs)
        if "[" in rhs2:
            write('\tmov\t\tedx,\teax')
            arraysplit = rhs2.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
            write('\tcmp\t\tedx,\teax')
        elif rhs2.isnumeric() == False:
            raddress = frame_Vars[rhs2][0]
            write('\tcmp\t\teax,\tDWORD PTR [rbp' + str(raddress) + ']')
        else:
            write('\tcmp\t\teax,\t' + rhs2)
        write('\tjne\t\tIF' + str(l_Count))
    elif "!=" in condition:
        innersplit = condition.split("!=")
        lhs = innersplit[0]
        lhs = lhs.strip()
        rhs1 = innersplit[1]
        rhssplit = rhs1.split(")")
        rhs2 = rhssplit[0]
        rhs2 = rhssplit[0].strip()
        print(rhs2)
        if "[" in lhs:
            arraysplit = lhs.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
        elif lhs.isnumeric() == False:
            laddress = frame_Vars[lhs][0]
            write('\tmov\t\teax,\tDWORD PTR [rbp' + str(laddress) + ']')
        else:
            write('\tmov\t\teax,\t' + lhs)
        if "[" in rhs2:
            write('\tmov\t\tedx,\teax')
            arraysplit = rhs2.split("[")
            arrayname = arraysplit[0]
            arraysplit2 = arraysplit[1].split("]")
            arrayindex = arraysplit2[0]
            if frame_Vars[arrayname][4] != 0:
                translate_array(arrayname, arrayindex, rlocal)
            else:
                translate_array(arrayname, arrayindex, rfunction)
            write('\tcmp\t\tedx,\teax')
        elif rhs2.isnumeric() == False:
            raddress = frame_Vars[rhs2][0]
            write('\tcmp\t\teax,\tDWORD PTR [rbp' + str(raddress) + ']')
        else:
            write('\tcmp\t\teax,\t' + rhs2)
        write('\tje\t\tIF' + str(l_Count))
    pc += 1
    write('IF' + str(l_Count) + ":")


def check_nested(x): 
    #checks to see if the for loop is nested or not
    #takes in the line that has the for loop (pc)
    #sets value of for_nest to True if this is a nested for loop
    #also records how many nested for loops and stores them in the variable number_of_nested_for
    global for_nested, number_of_nested_for
    for_open_bracket = 0
    for_closed_bracket = 0
    if_open_bracket = 0
    if_closed_bracket = 0
    most_recent = None

    counter = 0
    check = True
    while check: 
        for lines in source_Code:
            counter += 1
            if counter >= x and counter < len(source_Code): 
                
                if ("for" in source_Code[counter] and "{" in source_Code[counter]): 
                    
                    for_open_bracket += 1
                    most_recent = "for"
                elif ("for" in source_Code[counter] and "{" in source_Code[counter+1] and len(source_Code[counter])==1): 
                    for_open_bracket += 1
                    most_recent = "for"
                elif ("if" in source_Code[counter] and "{" in source_Code[counter]): 
                    if_open_bracket += 1
                    most_recent = "if"
                elif ("if" in source_Code[counter] and "{" in source_Code[counter+1] and len(source_Code[counter])==1): 
                    if_open_bracket += 1
                    most_recent = "if"
                elif ("}" in source_Code[counter]): 
                    if most_recent == "for": 
                        for_closed_bracket += 1
                    elif most_recent == "if": 
                        if_closed_bracket += 1
                if (for_open_bracket == for_closed_bracket):
                    check = False
                    break 
    number_of_nested_for = ((for_open_bracket + for_closed_bracket)/2)
    number_of_nested_if = ((if_open_bracket + if_closed_bracket)/2)

    if (number_of_nested_for == 1): 
        for_nested = False
    elif (number_of_nested_for > 1): 
        for_nested = True


def translate_For():
    global l_Count
    global pc
    global for_loop_counter 
    global for_limit
    strip_space = source_Code[pc].split("\n")
    i = 0
    
    if (for_loop_counter == 0): 
        for lines in source_Code: 
            if "for" in lines: 
                for_loop_counter += 1
        
    while i < len(strip_space):
        if "for" in strip_space[i]:
            for_limit += 1
            l_Count += 1
            label_for = l_Count + 1

            # Writes for loop prologue label
            write(".L" + str(l_Count) + ":")
            # Splits conditions in for(...)
            for_conditions = strip_space[i].split(";")

            # Finds comparator conditions in second index of for(...)
            # and translates into assembly
            if "<" in for_conditions[1]:
                split_condition = for_conditions[1].split(" ")
                left = split_condition[1]
                comparator = split_condition[2]
                right = split_condition[3]
                if left.isnumeric() == False:
                    laddress = frame_Vars[left][0]
                    write('\tcmp\t\tDWORD PTR [rbp' + str(laddress) + ']' + ', ' + str(int(right)-1))
                    write('\tjg\t' + "\t.L" + str(l_Count + 1))
                    i += 1
                else:
                    print("Compiler Error")
                    i += 1
            elif ">" in for_conditions[1]:
                split_condition = for_conditions[1].split(" ")
                left = split_condition[1]
                comparator = split_condition[2]
                right = split_condition[3]
                if left.isnumeric() == False:
                    laddress = frame_Vars[left][0]
                    laddress = frame_Vars[left][0]
                    write('\tcmp\t\tDWORD PTR [rbp' + str(laddress) + ']' + ', ' + str(int(right)))
                    write('\tjle\t' + "\t.L" + str(l_Count + 1))
                    i += 1
                else:
                    print("Compiler Error")
                    i += 1
            elif "<=" in for_conditions[1]:
                split_condition = for_conditions[1].split(" ")
                left = split_condition[1]
                comparator = split_condition[2]
                equal = split_condition[3]
                right = split_condition[4]
                if left.isnumeric() == False:
                    laddress = frame_Vars[left][0]
                    write('\tcmp\t\tDWORD PTR [rbp' + str(laddress) + ']' + ', ' + str(right))
                    i += 1
                else:
                    print("Compiler Error")
                    i += 1
            elif ">=" in for_conditions[1]:
                split_condition = for_conditions[1].split(" ")
                left = split_condition[1]
                comparator = split_condition[2]
                equal = split_condition[3]
                right = split_condition[4]
                if left.isnumeric() == False:
                    laddress = frame_Vars[left][0]
                    write('\tcmp\t\tDWORD PTR [rbp' + str(laddress) + ']' + ', ' + str(right))
                    i += 1
                else:
                    print("Compiler Error")
            i += 1

            # Translates for(){...}
            # Takes into account nested for loops
            local_Count = 0
            if ("{" in source_Code[pc] ):
                open_bracket_Count = 1  # pc gets incremented, so the initial '{' will not be detected
            else: 
                open_bracket_Count = 0
            close_bracket_Count = 0
            if for_loop_counter == 1:
                pc += 1
                translate_Body()
            
            if for_loop_counter > 1:
                while open_bracket_Count != close_bracket_Count:
                    pc += 1
                    local_Count += 1  
                    if "{" in source_Code[pc]:
                        open_bracket_Count += 1
                        local_Count += 1
                    elif "}" in source_Code[pc]:
                        close_bracket_Count += 1
                        local_Count += 1  
                    translate_Body()
            pc -= local_Count

            # Finds increment operations in third index of for(...)
            # and translates into assembly
            if "++" in for_conditions[2]:
                trim = for_conditions[2].replace(" ", "")
                split_condition = trim.split("++")
                left = split_condition[0]
                laddress = frame_Vars[left][0]
                if left.isnumeric() == False:
                    laddress = frame_Vars[left][0]
                    write('\tadd\t\tDWORD PTR [rbp' + str(laddress) + ']' + ", " + "1")
                    write('\tjmp\t' + "\t.L" + str(l_Count))
                    i += 1
                else:
                    print("Compiler error")
                    i += 1
            elif "--" in for_conditions[2]:
                trim = for_conditions[2].replace(" ", "")
                split_condition = trim.split("--")
                left = split_condition[0]
                if left.isnumeric() == False:
                    laddress = frame_Vars[left][0]
                    write('\tsub\t\tDWORD PTR [rbp' + str(laddress) + ']' + ", " + "1" + ']')
                    write('\tjmp\t' + "\t.L" + str(l_Count))       
                    i += 1
                else:
                    print("Compiler Error")
                    i += 1
            i += 1
        i += 1
        
    # Writes concluding label of all for loops
    if for_limit == for_loop_counter:
        write(".L" + str(label_for) + ":")

def getOffset(source):
    try:
        isinstance(source, str)
        return frame_Vars[source][0]
    finally:
        return source

def sieve(operand):
    ic(operand)
    if operand in frame_Vars:
        return frame_Vars[operand]
    else:
        return operand


def translate_Function_Call():
    global pc
    registers_64 = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
    registers= ['edi', 'esi', 'edx', 'ecx', 'r8d', 'r9d']
    ic(source_Code[pc])
    lhs = source_Code[pc].split("=")[0].strip()
    rhs = source_Code[pc].split("=")[1].split()[:-1]
    operands = [var.strip().replace(",", "") for var in rhs]
    i = 0
    function = operands[0][:-1]
    ic(function)
    for var in operands[1:]:
        if i < len(registers):
            if var.isdigit():
                write("\tmov \t{},\t{}".format(var, registers[i]))
            elif (frame_Vars[var][3] == True):
                translate_array(var, 0, arr_call)
                write("mov \t{}\t{}".format(registers_64[i]), "rax")
                i += 1
            elif var in frame_Vars:
                write("\tmov \tDOWRD PTR [rbp{}],\t{}\t; {}".format(frame_Vars[var][0], registers[i], var))
            else:
                print("Not recognized")
            i += 1
        else:
            write("\tpush \t{}".format(var))
    fn_Call_name = var[:-1]
    write("\tcall \t{}".format(function))
    write("\tmov \tDWORD PTR [rbp{}],\t eax ; ret val of called fn".format(frame_Vars[lhs][0]))

    pc += 1


def translate_Return():
    global l_Count
    global pc
    strip_space = source_Code[pc].split("\n")
    i = 0
    j = 0
 
    while i < len(strip_space):
        if "return" in strip_space[i]:
            # Stores the line containing return from end to start into variable
            # ex: return a; => ;a nruter
            reverseReturn = strip_space[i][::-1]
            variable = ""
            # Increments until variable reaches a space, where it is trimmed so only the variable to be read remains
            # and is translated into assembly
            while j < len(reverseReturn):
                variable += reverseReturn[j]
                if reverseReturn[j] == " ": 
                    variable = variable.rstrip()
                    variable = variable.strip(";")
                    if variable.isnumeric() == False:
                        address = frame_Vars[variable][0]
                        write('\tmov\t\teax, DWORD PTR [rbp' + str(address) + ']')
                        i += 1
                        j += 1
                        break
                    else:
                        print("Compiler Error")
                        i += 1
                        j += 1
                        break
                j += 1
        i += 1
    pc += 1

# Write function header to file
def write_Head():
    function_Head = function_Names[-1] + " (" # Simply takes most recent name
    for arg in arg_Queue:
        function_Head += 'int'
        if(frame_Vars[arg][2] == True):
            function_Head += '*'
        function_Head += ', '
    function_Head = function_Head.rstrip(' ,')
    function_Head += '):'
    write(function_Head)

def translate_array(name, index, type_of_handling):

    #get base address of array
    if name in frame_Vars:
        base_address = frame_Vars[name][0]
    else:
        print("array was not declared/ allocated")
        sys.exit()

    index_address = None

    #perform a check to see whether the index is numeric or a variable
    if (isinstance(index, int)):
        #if the index is numeric, find the array address of the given index by finding the offset
        offset_address = base_address - (index*4)
    else:
        #if the index is a variable, then find the array address of the variable
        for variables in frame_Vars:
            if index in frame_Vars:
                index_address = frame_Vars[index][0]
            else:
                print("variable index was not declared/ allocated")
                sys.exit()

    #store base address into argument
    if (type_of_handling == arr_call):
       write('\tlea\t\trax, [rbp' + str(base_address) + ']')
       #the function_call function will take care of storing rax into the argument register

    #read local array
    elif (type_of_handling == rlocal):
        if (index_address != None):
            write('\tlea\t\trax, [rbp' + str(base_address) + ']')
            write('\tmov\t\teax, DWORD PTR [rbp' + str(index_address) + ']')
            write('\tmov\t\teax, DWORD PTR [rax+eax*4]')
        else:
            write('\tmov\t\teax, DWORD PTR [rbp' + str(offset_address) + ']')

    #write to local array
    elif (type_of_handling == wlocal):

        if (index_address != None):
            write('\tlea\t\trax, [rbp' + str(base_address) + ']')
            write('\tmov\t\tedx, DWORD PTR [rbp' + str(index_address) + ']')
            #arithmetic function has to store value into eax
            write('\tmov\t\tDWORD PTR [rax+edx*4], eax')
        else:
            #arithmetic value has to be stored in eax at this point to proceed
            write ('\tmov\t\tDWORD PTR [rbp' + str(offset_address) + '], eax')

    #read array from function parameter
    elif (type_of_handling == rfunction):
        if (index_address != None):
            write('\tlea\t\trax, [rbp' + str(base_address) + ']')
            write('\tmov\t\teax, DWORD PTR [rbp' + str(index_address) + ']')
            write('\tmov\t\teax, DWORD PTR[rax+4*eax]')

        else:
            write('\tlea\t\trax, [rbp' + str(base_address) + ']')
            write('\tmov\t\teax, ' + str(index))
            write('\tmov\t\teax, DWORD PTR [rax+4*eax]')

    #write to array from function parameter
    elif (type_of_handling == wfunction):
        if (index_address != None):
            write('\tlea\t\trax, [rbp' + str(base_address) + ']')
            write('\tmov\t\tedx, DWORD PTR [rbp' + str(index_array) + ']')
            #arithmetic value should be stored in eax to proceed
            write('\tmov\t\tDWORD PTR [rax+4*edx], eax]')
        else:
            write('\tlea\t\trax, [rbp' + str(base_address) + ']')
            write('\tmov\t\tedx, ' + str(index))
            #arithmetic value should be stored in eax to proceed
            write('\tmov\t\tDWORD PTR [rax+4*edx], eax')
    else:
        print("No handling for array specified")
        sys.exit()


def translation_driver():
    global source_Code, pc

    while(pc < len(source_Code) ):

        #check to see what line in the source code we are reading
        print("current PC at start of function: ", pc)

        #if "int" is in the line, then it is a function header
        if "int" in source_Code[pc]:
            translate_Function()
            
        #if there is no "int" in the line, then pc has not been incremented properly
        #and this is not a function header
        #print out where the error occurs
        elif (len(source_Code[pc]) > 0):
            print ("Error with PC counter. not incremented properly")
            print ("PC is: ", pc)
            print ("PC line is: ", source_Code[pc])
            sys.exit()
        else:
            print("Error: ran out of code")
            sys.exit()
        print("PC at end of function: ", pc)
        # TODO: pc += 1 is only here to test the function. Needs to be removed
        #pc += 1

# Controls all functions to translate a full function
def translate_Function():
    global pc
    parse_Func_Head()
    pc +=1
    check_Local_Decs()
    # print(local_Queue)
    write_Head()
    write_Func_Prologue()
    ic(frame_Vars)
    translate_Body()

    # Need to make this call to complete this function

    write("\tleave")
    write("\tret")
    reset_Globals()

# Controls moving through file, translating all functions
#def translation_Driver():

def translate_array(name, index, instrtype):
   """
   input: name and index of array
   output:
   """
   frame_Vars[name]
   pass

# Main
# Handles command line input, source file reading
if __name__ == "__main__":

    # File names provided on command line - close if insufficient arguments
    if(len(sys.argv) != 3):
        print('Usage: ./compiler [INPUT FILE NAME] [OUTPUT FILE NAME]')
        sys.exit()

    source_Filename = sys.argv[1]
    output_Filename = sys.argv[2]

    # Attempt to open source and output files
    try:
        source = open(source_Filename, 'r')
    except:
        print('Source file does not exist')
        sys.exit()

    try:
        out = open(output_Filename, 'w')
    except:
        print('Invalid output filename')
        sys.exit()

    # Read in source code - split on \n and discard blank lines; close source
    source_Raw_Text = source.read()
    source.close()

    # Check for empty source
    if(len(source_Raw_Text) == 0):
        print('Empty source file')
        sys.exit()

    source_Code = [line for line in source_Raw_Text.split('\n') if len(line) > 0]

    # Translate
    # translate_Function() # NEEDS TO BE REPLACED WITH translation_Driver()
    translation_driver()

    # translate_array('c')

    # Print globals for debugging
    #print(pc)
    #print(rsp)
    #print(function_Names)
    #print(arg_Queue)
    #print(local_Queue)

    # Close output file
    out.close()