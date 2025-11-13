# function to split the txt file of SQL commands by the semicolon delimiter
def parse_sql_txt(file_path):
    """
    Parses a simple SQL file by splitting on the semicolon delimiter.
    This method does not handle comments or semicolons within strings.
    """
    try:
        with open(file_path, 'r') as f:
            sql_txt = f.read()
        
        # Split the content by the semicolon delimiter
        statements = sql_txt.split(';')
        
        print(f"--- Parsing SQL from: {file_path} ---")
        for i, statement in enumerate(statements, 1):
            clean_statement = statement.strip()
            
            # Skip empty statements
            if clean_statement:
                print(f"--- Statement {i} ---")
                print(clean_statement + ";") # Add semicolon back for readability
                print("-" * 20)

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# main driver function
if __name__ == "__main__":
    input_file = "input.txt"
    parse_simple_sql_file(input_file)
