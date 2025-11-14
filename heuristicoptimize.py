# function to split the txt file of SQL commands by the semicolon delimiter
def parse_sql_txt(file_path):
    try:
        # open file and read contents
        with open(file_path, 'r') as f:
            sql_txt = f.read()
        
        # Split the content by the semicolon delimiter and strip each statement
        statements = [s.strip() for s in sql_txt.split('\n') if s.strip()]

        
        # strip statements to clean
        print(f"--- Parsing SQL from: {file_path} ---") # FOR DEBUG ONLY
        for i, statement in enumerate(statements, 1):
            clean_statement = statement.strip()
            
            # Skip empty statements
            if clean_statement:
                # FOR DEBUG ONLY
                '''
                print(f"--- Statement {i} ---") 
                print(clean_statement)
                print("-" * 20)
                '''

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
    # return 
    return statements

# main driver function
if __name__ == "__main__":
    # set input file
    input_file = "input.txt"
    non_comment_lines = 0
    # list to hold non-comment lines
    statements = []
    # list to hold project clauses from select statements
    project_clauses = []
    # list to hold where clauses
    where_clauses = []
    # list to hold from clauses aka relevant tables
    tables = []
    selectivity_clause = {} # dict for holding clause:selectivity pairs (where selectivity of 0 is low and 1 is high)
    # list for join clauses (foreign keys)
    join_clauses = []
    # list for select clauses
    select_clauses = []
    # list to store tables pairs that are joined
    join_tables = []

    # parse input file into each line
    all_statements = parse_sql_txt(input_file)

    # parse each statement from all_statements to statements, removing comments
    for i, statement in enumerate(all_statements, 1):
        # discard lines that start with two dashes '--' (comments)
        if statement[0] == "-" and statement[1] == "-":
            # print(f"Comment: {statement}") # FOR DEBUG ONLY
            pass
        # add non-comment lines to new list
        else:
            statements.append(statement)
            non_comment_lines = non_comment_lines+1
            # print(f"Line {non_comment_lines}: {statement}") # FOR DEBUG ONLY
    
    # parses/sorts/filters each statement from statements to each clause list
    for i, statement in enumerate(statements, 1):
        # filter project_clauses (PROJECT clauses)
        if statement[0] == "S" and statement[1] == "E" and statement[2] == "L":
            s = statement[7:].split(", ")
            for i in s:
                project_clauses.append(s)
            # print(f"Project clauses: {s}") # FOR DEBUG ONLY
        # filter where_clauses (SELECT clauses)
        if statement[0] == "W" and statement[1] == "H" and statement[2] == "E" and statement[3] == "R" and statement[4] == "E":
            where_clauses.append(statement[6:-3])
            for k in range(i+1, len(statements)-1):
                s = statements[k]
                if ">" in s or "<" in s or "=" in s:
                    if "AND" in s:
                        where_clauses.append(s[:-3])
                    else:
                        where_clauses.append(s)
            # for j, c in enumerate(where_clauses, 1):
                # print(f"Where clause: {c}") # FOR DEBUG ONLY
        # filter tables from FROM statement (JOINS needed)
        if statement[0] == "F" and statement[1] == "R" and statement[2] == "O" and statement[3] == "M":
            tables = statement[5:].split(", ")
            for j, t in enumerate(tables, 1):
                # print(f"table: {t}") # FOR DEBUG ONLY
                tables[j-1] = t[-1:]
    
    # parses each WHERE clause to a join condition and selectivity
    for i, c in enumerate(where_clauses, 1):
        # prioritize equality for selectivity
        if "=" in c:
            # print(f"where_clause[{i}] = {c} with \"=\" operator: selectivity = low (0)") # FOR DEBUG ONLY
            selectivity_clause[c] = 0
            # print(f"selectivity of clause {c} is low {selectivity_clause[c]}") # FOR DEBUG ONLY
            
            # check if foreign key comparison (for join clause)
            arguments = c.split("=")
            # print(f"arguments: {arguments}") # FOR DEBUG ONLY
            if "." in arguments[0] and "." in arguments[1]:
                # print(f"foreign key join clause detected: {c}") # FOR DEBUG ONLY
                join_clauses.append(c)
                argument1 = arguments[0]
                argument2 = arguments[1]
                join_tables.append(argument1[0:1])
                join_tables.append(argument2[0:1])
                print(f"join_clauses: {join_tables}") # FOR DEBUG ONLY
            else:
                select_clauses.append(c)
                print(f"select_clause: {c}") # FOR DEBUG ONLY
        # comparison operators with greater selectivity
        else:
            # print(f"where_clause[{i}] = {c} with comparison operator: selectivity = high (1)") # FOR DEBUG ONLY
            selectivity_clause[c] = 1
            # print(f"selectivity of clause {c} is high {selectivity_clause[c]}") # FOR DEBUG ONLY
            select_clauses.append(c)
            print(f"select_clause: {c}") # FOR DEBUG ONLY
            
    # print canonical tree given project_clauses, where_clauses, tables
    print("Printing canonical query tree from given SQL txt:")
    print(f"Select clauses: {select_clauses} ({len(select_clauses)})")
    print(f"Join clauses: {join_clauses} ({len(join_clauses)})") # FOR DEBUG ONLY
    print(f"Join tables: {join_tables} ({len(join_tables)})") # FOR DEBUG ONLY
    
    
    # print first join condition
    for i, t in enumerate(join_tables):
        if i < len(join_clauses)/2:
            print(f"   X({join_clauses[0]})  ", end="")
        if i == len(join_tables)-1:
            print("  \\")
    
    # print connecting lines for next level with first join
    for i, t in enumerate(join_tables):
        if i < len(join_clauses)/2:
            print("    /\\    ", end="")
        if i == len(join_clauses)-1:
            for j in range(0, len(join_clauses[0])):
                print(" ", end="")
            print(" \\")
    
    # print connecting lines for bottom level
    for i, t in enumerate(tables):
        if i < len(tables)-2:
            print("   /  \   ", end="")
        if i == len(tables)-1:
            for j in range(0, len(join_clauses[0])):
                print(" ", end="")
            print("  \\")
    
    # print each table letter with a two space gap on either side
    # print join tables first
    for i, t in enumerate(join_tables):
        print(f"  {t}  ", end="")
    # print the other tables
    for i, t in enumerate(tables): 
        if t not in join_tables:
            for j in range(0, len(join_clauses[0])):
                print(" ", end="")
            print(f"  {t}  ", end="")
