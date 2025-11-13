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
    # list to hold select statements
    select_statements = []
    # list to hold where clauses
    where_clauses = []
    # list to hold from clauses aka relevant tables
    tables = []
    selectivity_clause = {} # dict for holding clause:selectivity pairs (where selectivity of 0 is low and 1 is high)

    # parse input file into each line
    all_statements = parse_sql_txt(input_file)

    # parse each statement from all_statements to statements, removing comments
    for i, statement in enumerate(all_statements, 1):
        # discard lines that start with two dashes '--' (comments)
        if statement[0] == "-" and statement[1] == "-":
            print(f"Comment: {statement}") # FOR DEBUG ONLY
        # add non-comment lines to new list
        else:
            statements.append(statement)
            non_comment_lines = non_comment_lines+1
            # print(f"Line {non_comment_lines}: {statement}") # FOR DEBUG ONLY
    
    # parses/sorts/filters each statement from statements to each clause list
    for i, statement in enumerate(statements, 1):
        # filter select_statements (PROJECT clauses)
        if statement[0] == "S" and statement[1] == "E" and statement[2] == "L":
            s = statement[7:].split(", ")
            for i in s:
                select_statements.append(s)
            print(f"Project clauses: {s}")
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
            for j, c in enumerate(where_clauses, 1):
                print(f"Where clause: {c}")
        # filter tables from FROM statement (JOINS needed)
        if statement[0] == "F" and statement[1] == "R" and statement[2] == "O" and statement[3] == "M":
            tables = statement[5:].split(", ")
            for j, t in enumerate(tables, 1):
                print(f"table: {t}")
    
    # parses each WHERE clause to a join condition
    for i, c in enumerate(where_clauses, 1):
        # prioritize equality for selectivity
        if "=" in c:
            print(f"where_clause[{i}] = {c} with \"=\" operator: selectivity = low (0)") # FOR DEBUG ONLY
            selectivity_clause[c] = 0
            print(f"selectivity of clause {c} is low {selectivity_clause[c]}") # FOR DEBUG ONLY
        # comparison operators with greater selectivity
        else:
            print(f"where_clause[{i}] = {c} with comparison operator: selectivity = high (1)") # FOR DEBUG ONLY
            selectivity_clause[c] = 1
            print(f"selectivity of clause {c} is high {selectivity_clause[c]}") # FOR DEBUG ONLY
        
