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
            parse_where(where_clause.group(1))
        group_by_clause = re.search(r"GROUP BY\s+(.*?)\s+(HAVING|;)", sql_txt_remove_line, re.IGNORECASE)
        if group_by_clause:
            print(f"Group By Clause: {group_by_clause.group(1)}") #testing
            parse_group_by(group_by_clause.group(1))
        having_clause = re.search(r"HAVING\s+(.*?)\s+(ORDER BY|;)", sql_txt_remove_line, re.IGNORECASE)
        if having_clause:
            print(f"Having Clause: {having_clause.group(1)}") #testing
            parse_having(having_clause.group(1))
        order_by_clause = re.search(r"ORDER BY\s+(.*?);", sql_txt_remove_line, re.IGNORECASE)
        if order_by_clause:
            print(f"Order By Clause: {order_by_clause.group(1)}") #testing
            parse_order_by(order_by_clause.group(1))


        

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
    # return 
    return

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
    # Parse the WHERE clause into structured predicates.
    # Supports AND/OR, parentheses, and comparison operators.

    if not statement or not statement.strip():
        return []

    s = statement.strip()

    operators = [
        r">=", r"<=", r"<>", r"!=", r"=", r">", r"<",
        r"LIKE", r"IN", r"BETWEEN", r"IS NOT", r"IS"
    ]
    operator_regex = "|".join(operators)

    token_regex = re.compile(
        rf"""
        (\()                    |   # "("
        (\))                    |   # ")"
        \b(AND|OR)\b            |   # logical operators

        (\S+)\s*                # left operand (ANYTHING except whitespace)

        ({operator_regex})      # operator

        \s*

        (\S+)                   # right operand (ANYTHING except whitespace)
        """,
        re.IGNORECASE | re.VERBOSE
    )

    tokens = []
    idx = 0

    while idx < len(s):
        m = token_regex.match(s, idx)
        if not m:
            if s[idx].isspace():
                idx += 1
                continue
            raise ValueError(f"Unrecognized token in WHERE/HAVING clause at: {s[idx:]}")

        g = m.groups()

        if g[0]:
            tokens.append("(")
        elif g[1]:
            tokens.append(")")
        elif g[2]:
            tokens.append(g[2].upper())
        else:
            tokens.append({
                "left": g[3],
                "operator": g[4].upper(),
                "right": g[5]
            })

        idx = m.end()

    print("WHERE Parsed Tokens:", tokens)
    return tokens


def parse_group_by(statement):
    # Parses the GROUP BY clause.
    # Returns a list of grouping expressions.
    # Example: ["A.dept", "A.role", "DATE(A.hire_date)"]

    if not statement or not statement.strip():
        return []

    # Split by commas, preserve expressions
    groups = [g.strip() for g in statement.split(",")]

    print("GROUP BY Parsed:", groups)
    return groups

def parse_having(statement):
    # Parses the HAVING clause into structured predicate tokens.
    # Reuses the same logic as parse_where.
    
    if not statement or not statement.strip():
        return []

    print("Parsing HAVING:", statement)
    return parse_where(statement)

def parse_order_by(statement):
    # Parse ORDER BY clause.
    # Returns list of dicts:
    #     { "expr": <expression>, "direction": "ASC"/"DESC" }
    
    if not statement or not statement.strip():
        return []

    # Split on commas at top level
    parts = [p.strip() for p in statement.split(",")]

    results = []
    for part in parts:
        # Detect ASC/DESC (default ASC)
        m = re.match(r"(.+?)\s+(ASC|DESC)$", part, re.IGNORECASE)
        if m:
            expr = m.group(1).strip()
            direction = m.group(2).upper()
        else:
            expr = part
            direction = "ASC"  # SQL default

        results.append({
            "expr": expr,
            "direction": direction
        })

    print("ORDER BY Parsed:", results)
    return results





# main driver function
if __name__ == "__main__":
    # set input file
    input_file = "input2.txt"
    
    all_statements = parse_sql_txt(input_file)
