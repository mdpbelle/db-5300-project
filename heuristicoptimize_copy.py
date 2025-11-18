import re

AGGREGATE_FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'}
JOINS = {'INNER JOIN', 'LEFT OUTER JOIN', 'RIGHT OUTER JOIN', 'FULL OUTER JOIN', 'JOIN'}

# function to split the txt file of SQL commands by the semicolon delimiter
def parse_sql_txt(file_path):
    try:
        # open file and read contents
        with open(file_path, 'r') as f:
            sql_txt = f.read()
        
        sql_txt_remove_line = sql_txt.replace('\n', ' ')
        print(sql_txt_remove_line)
        # Split the content by semicolon and SQL operation keywords
        # Extracts each part of the SQL statement (excluding the keyword)
        #
        # The regex is a pain to read, but it basically looks for the keyword that starts an operation
        # it then captures everything after the keyword until hitting another keyword or ;
        # then passes that to the respective parser function
        select_clause = re.search(r"SELECT\s+(.*?)\s+FROM", sql_txt_remove_line, re.IGNORECASE)
        print(f"Select Clause: {select_clause.group(1)}") #testing
        parse_select(select_clause.group(1))
        from_clause = re.search(r"FROM\s+(.*?)(?=\s+WHERE|\s+GROUP BY|\s+HAVING|\s+ORDER BY|\s*;|$)", sql_txt_remove_line, re.IGNORECASE)
        print(f"From Clause: {from_clause.group(1)}") #testing
        parse_from(from_clause.group(1))
        where_clause = re.search(r"WHERE\s+(.*?)\s+(GROUP BY|;)", sql_txt_remove_line, re.IGNORECASE)
        if where_clause:
            print(f"Where Clause: {where_clause.group(1)}") #testing
        group_by_clause = re.search(r"GROUP BY\s+(.*?)\s+(HAVING|;)", sql_txt_remove_line, re.IGNORECASE)
        if group_by_clause:
            print(f"Group By Clause: {group_by_clause.group(1)}") #testing
        having_clause = re.search(r"HAVING\s+(.*?)\s+(ORDER BY|;)", sql_txt_remove_line, re.IGNORECASE)
        if having_clause:
            print(f"Having Clause: {having_clause.group(1)}") #testing
        order_by_clause = re.search(r"ORDER BY\s+(.*?);", sql_txt_remove_line, re.IGNORECASE)
        if order_by_clause:
            print(f"Order By Clause: {order_by_clause.group(1)}") #testing


        statements = [s.strip() for s in sql_txt.split('\n') if s.strip()]

        for statement in statements:
            print(statement)
        
        
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

def parse_select(statement):
    # extract project clauses from SELECT statement
    projects_dict = load_projects(statement)
    return projects_dict

def load_projects(statement):
    # Handles the parsing of the projection attributes from the SELECT clause
    # If there are aggregate functions, it handles those as well
    # If selecting all attributes (*), it handles that case too
    # 
    # Creates a dictionary where keys are table names, and attributes are put into lists as values
    # If no table, uses "*" as the key

    projects = re.split(r"\s*,\s*", statement) #split projects by comma

    # print(f"Projects: {projects}")  # DEBUG
    
    projects_dict = {}

    # if return all attributes (SELECT *)
    if statement == "*":
        projects_dict["*"] = ["*"]
        return projects_dict

    for p in projects:

        # Aggregate function handling (COUNT, SUM, AVG, MIN, MAX)
        if '(' in p:
            func_name = p[:p.index('(')].upper()

            if func_name in AGGREGATE_FUNCTIONS:
                inner = p[p.index('(')+1 : p.rindex(')')].strip()

                # inside is "A.col"
                if "." in inner:
                    table, attribute = inner.split(".", 1)
                else:
                    # default table : *
                    table = "*"
                    attribute = inner

                projects_dict.setdefault(table, []).append(f"{func_name}({attribute})")
                continue # proceed to next projection

        # If no table specified, use a default * in the dict
        if "." not in p:
            p = "*." + p

        # table.attr, uses table as keyword and adds attribute to list
        project_table, project_attribute = p.split(".", 1)

        projects_dict.setdefault(project_table, []).append(project_attribute)

    # DEBUG
    for key, value in projects_dict.items():
        print(key, "=", value)

    return projects_dict


def parse_from(statement):
    # parses FROM clause to extract tables and joins
    # first checks if it is a cartesian product (comma separated tables)
    # if not, parses joins iteratively and checks join type
    # produces a dict with "tables" and "joins" keys.
    # Join values are dicts with type, left_table, right_table, condition


    from_clause = {"tables": {}, "joins": []}
    
    # Remove extra whitespace
    statement = ' '.join(statement.strip().split())
    
    print(f"Parsing FROM clause: {statement}")  # DEBUG

    if ',' in statement:
        # handle cartesian products
        tables = [t.strip() for t in statement.split(',')]
        for t in tables:
            # Regex to match table with optional alias: "TableName Alias"
            table_alias = re.compile(r"(\w+)(?:\s+(\w+))?", re.IGNORECASE)
            table_name = table_alias.match(t)
            if not table_name:
                raise ValueError(f"Cannot parse table in FROM clause: {t}")
            name, alias = table_name.groups()
            alias = alias or name
            from_clause["tables"][alias] = name
        print(f"FROM clause parsed (cartesian products): {from_clause}")  # DEBUG
        return from_clause


    # Regex to match first table: "TableName Alias"
    first_table_regex = re.compile(r"(\w+)(?:\s+(\w+))?", re.IGNORECASE)
    m = first_table_regex.match(statement)
    if not m:
        raise ValueError("Cannot parse first table in FROM clause")
    
    table_name, alias = m.groups()
    alias = alias or table_name
    from_clause["tables"][alias] = table_name
    last_alias = alias
    
    # Remove the matched first table from statement
    statement = statement[m.end():].strip()
    
    
    # Regex to match JOINs
    join_regex = re.compile(
        r"(INNER|LEFT OUTER|LEFT|RIGHT|FULL OUTER)?\s*JOIN\s+(\w+)\s+(\w+)\s+ON\s+([^ ]+(?:\s*=\s*[^ ]+)*)",
        re.IGNORECASE
    )
    
    while statement:
        jm = join_regex.match(statement)
        if not jm:
            break  # no more joins
        
        join_type, right_table, right_alias, condition = jm.groups()
        join_type = (join_type or "JOIN").upper()
        
        from_clause["tables"][right_alias] = right_table
        from_clause["joins"].append({
            "type": join_type,
            "left_table": last_alias,
            "right_table": right_alias,
            "condition": condition.strip()
        })
        
        last_alias = right_alias
        statement = statement[jm.end():].strip()
    print(f"FROM clause parsed: {from_clause}")  # DEBUG
    return from_clause

def parse_where(statement):
    # extract where clause from WHERE statement
    where_clause = statement[6:]
    where_clauses.append(where_clause)
    return where_clause

# main driver function
if __name__ == "__main__":
    # set input file
    input_file = "input3.txt"
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
            # remove semi-colon
            if ";" in statement:
                statement = statement[0:-1]
            statements.append(statement)
            non_comment_lines = non_comment_lines+1
            print(f"Line {non_comment_lines}: {statement}") # FOR DEBUG ONLY
    
    # parses/sorts/filters each statement from statements to each clause list
    for i, statement in enumerate(statements, 1):
        # filter project_clauses (PROJECT clauses)
        print(statement)
        if statement[0:6] == "SELECT":
            parse_select(statement)
        elif statement[0:5] == "WHERE":
            parse_where(statement)
        elif statement[0:4] == "FROM":
            parse_from(statement)
    
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
                join_table1 = argument1[0:1]
                join_table2 = argument2[0:1]
                # check for duplicates before adding tables
                if join_table1 not in join_tables:
                    join_tables.append(join_table1)
                if join_table2 not in join_tables:
                    join_tables.append(join_table2)
                # print(f"join_clauses: {join_tables}") # FOR DEBUG ONLY
            else:
                select_clauses.append(c)
                # print(f"select_clause: {c}") # FOR DEBUG ONLY
        # comparison operators with greater selectivity
        else:
            # print(f"where_clause[{i}] = {c} with comparison operator: selectivity = high (1)") # FOR DEBUG ONLY
            selectivity_clause[c] = 1
            # print(f"selectivity of clause {c} is high {selectivity_clause[c]}") # FOR DEBUG ONLY
            select_clauses.append(c)
            # print(f"select_clause: {c}") # FOR DEBUG ONLY
            
    print(f"Project clauses: {project_clauses} ({len(project_clauses)})")
    print(f"Select clauses: {select_clauses} ({len(select_clauses)})")
    print(f"Join clauses: {join_clauses} ({len(join_clauses)})") # FOR DEBUG ONLY
    print(f"Tables: {join_tables} ({len(join_tables)})") # FOR DEBUG ONLY
    print()
    
    # print canonical tree given project_clauses, where_clauses, tables
    print("Printing canonical query tree from given SQL txt:")
    print()
    
    # print project conditions
    print("Project(", end="")
    for i, c in enumerate(project_clauses, 1):
        if i != len(project_clauses):
            print(f"{project_clauses[i-1]} AND ", end="")
        else:
            print(f"{project_clauses[i-1]}", end="")
    print(")")
    
    # print vertical line from select to project
    for i in range(0,1):
        for j in range(0, len(tables)+1):
            print(" ", end="")
        print("|")
    
    # print select conditions (all where clauses)
    print("Select(", end="")
    for i, c in enumerate(where_clauses, 1):
        if i != len(where_clauses):
            print(f"{c} AND ", end="")
        else:
            print(f"{c}", end="")
    print(")")
    
    # print vertical line from final join to select
    for j in range(0, 1):
        for i in range(0, len(tables)+1):
            print(" ", end="")
        print("|")
    
    # print second join condition (if there is a third table to join)
    if len(tables) >= 3:
        print(f"    X")
    
    # print lines to next join condition
    starting_spaces = 4
    between_spaces = 0
    while between_spaces < len(tables):
        # print starting spaces on same line
        starting_spaces = starting_spaces-1
        for i in range(0, starting_spaces):
            print(" ", end="")
        # print right slash on same line
        print("/", end="")
        # print between spaces on same line
        for i in range(0, between_spaces):
            print(" ", end="")
        # print left slash on same line
        print("\\")
        between_spaces = between_spaces+2
    
    # print first join condition
    for i, t in enumerate(join_tables):
        if i < len(join_clauses)/2:
            print(f"  X   ", end="")
        if i == len(join_tables)-1:
            print("\\")
    
    # print connecting lines for next level with first join
    for i, t in enumerate(join_tables):
        if i < len(join_clauses)/2:
            print("  /\\   ", end="")
        if i == len(join_clauses)-1:
            print("\\")
    
    # print connecting lines for bottom level
    for i, t in enumerate(tables):
        if i < len(tables)-2:
            print(" /  \   ", end="")
            print("\\")
    
    # print each table letter with a two space gap on either side
    # print first two tables first
    #print(f"{join_tables[0]}  ", end="")
    #print(f"  {join_tables[1]}  ", end="")
    # print the other tables
    for i in range(2, len(join_tables)):
        print(f" {join_tables[i]} ", end="")
        
