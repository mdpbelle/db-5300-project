# function to split the txt file of SQL commands by the semicolon delimiter
def parse_sql_txt(file_path):
    try:
        # open file and read contents
        with open(file_path, 'r') as f:
            sql_txt = f.read()
        
        # Split the content by the semicolon delimiter and strip each statement
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]

        # return 
        return statements
        
        # strip statements to clean
        print(f"--- Parsing SQL from: {file_path} ---") # FOR DEBUG ONLY
        for i, statement in enumerate(statements, 1):
            clean_statement = statement.strip()
            
            # Skip empty statements
            if clean_statement:
                # FOR DEBUG ONLY
                print(f"--- Statement {i} ---") 
                print(clean_statement + ";") # Add semicolon back for readability
                print("-" * 20)

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# main driver function
if __name__ == "__main__":
    # set input file
    input_file = "input.txt"

    # parse input file into each line
    statements = parse_simple_sql_file(input_file)

    # parse each statement
    for i, statement in enumerate(statements, 1):
        if statement[0:1] == "--":
            print(f"Comment: {statement}")
    # discard lines that start with two dashes '--' (comments)
     
    # filter select clauses
    # filter project clauses
    # filter cartesian products
