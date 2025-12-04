import re
from graphviz import Digraph

AGGREGATE_FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'}
JOINS = {'INNER JOIN', 'LEFT OUTER JOIN', 'RIGHT OUTER JOIN', 'FULL OUTER JOIN', 'JOIN'}

# function to split the txt file of SQL commands by the semicolon delimiter
def parse_sql_txt(file_path):
    try:
        # open file and read contents
        with open(file_path, 'r') as f:
            sql_txt = f.read()
        
        sql_txt_remove_line = sql_txt.replace('\n', ' ')

        # Remove everything up until the first SELECT
        sql_txt_remove_line = re.sub(r'^(.*?)SELECT\s+', 'SELECT ', sql_txt_remove_line, flags=re.IGNORECASE)

        # Remove comments -- anything after -- to end of line
        sql_txt_remove_line = re.sub(r'--.*?(\r\n|\r|\n)', ' ', sql_txt_remove_line)

        # print(sql_txt_remove_line)
        # Split the content by semicolon and SQL operation keywords
        # Extracts each part of the SQL statement (excluding the keyword)
        #
        # The regex is a pain to read, but it basically looks for the keyword that starts an operation
        # it then captures everything after the keyword until hitting another keyword or ;
        # then passes that to the respective parser function
        select_clause = re.search(r"SELECT\s+(.*?)\s+FROM", sql_txt_remove_line, re.IGNORECASE)
        #print(f"Select Clause: {select_clause.group(1)}") #testing
        select_parsed = parse_select(select_clause.group(1))
        from_clause = re.search(r"FROM\s+(.*?)(?=\s+WHERE|\s+GROUP BY|\s+HAVING|\s+ORDER BY|\s*;|$)", sql_txt_remove_line, re.IGNORECASE)
        #print(f"From Clause: {from_clause.group(1)}") #testing
        from_parsed = parse_from(from_clause.group(1))
        where_clause = re.search(r"WHERE\s+(.*?)\s*(GROUP BY|;)", sql_txt_remove_line, re.IGNORECASE)
        where_parsed = None
        if where_clause:
            #print(f"Where Clause: {where_clause.group(1)}") #testing
            where_parsed = parse_where(where_clause.group(1))
        group_by_clause = re.search(r"GROUP BY\s+(.*?)\s+(HAVING|;)", sql_txt_remove_line, re.IGNORECASE)
        group_by_parsed = None
        if group_by_clause:
            #print(f"Group By Clause: {group_by_clause.group(1)}") #testing
            group_by_parsed = parse_group_by(group_by_clause.group(1))
        having_clause = re.search(r"HAVING\s+(.*?)\s+(ORDER BY|;)", sql_txt_remove_line, re.IGNORECASE)
        having_parsed = None
        if having_clause:
            #print(f"Having Clause: {having_clause.group(1)}") #testing
            having_parsed = parse_having(having_clause.group(1))
        order_by_clause = re.search(r"ORDER BY\s+(.*?);", sql_txt_remove_line, re.IGNORECASE)
        order_by_parsed = None
        if order_by_clause:
            #print(f"Order By Clause: {order_by_clause.group(1)}") #testing
            order_by_parsed = parse_order_by(order_by_clause.group(1))

        # Return all parsed components as a dictionary of clauses
        return {
            "select": select_parsed, # dict of projections
            "from": from_parsed, # dict of tables and joins
            "where": where_parsed, # list of selection predicates
            "group by": group_by_parsed, # list of grouping expressions
            "having": having_parsed, # list of having predicates
            "order by": order_by_parsed # list of order by expressions
        }

        

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
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
            func_name = p[:p.index('(')].upper() # get function name

            if func_name in AGGREGATE_FUNCTIONS: # check if it is an aggregate function
                inner = p[p.index('(')+1 : p.rindex(')')].strip() # strip out the inner attribute

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
    # for key, value in projects_dict.items():
    #     print(key, "=", value)

    return projects_dict


def parse_from(statement):
    # parses FROM clause to extract tables and joins
    # first checks if it is a cartesian product (comma separated tables)
    # if not, parses joins iteratively and checks join type
    # produces a dict with "tables" and "joins" keys.
    # Join values are dicts with type, left_table, right_table, condition


    from_clause = {"tables": {}, "joins": []} # initialize from clause dict, tables are dict, joins are list of dicts
    
    # Remove extra whitespace
    statement = ' '.join(statement.strip().split())
    
    # print(f"Parsing FROM clause: {statement}")  # DEBUG

    if ',' in statement:
        # handle cartesian products
        tables = [t.strip() for t in statement.split(',')]
        for t in tables:
            # Regex to match table with optional alias: "TableName Alias"
            table_alias = re.compile(r"(\w+)(?:\s+(\w+))?", re.IGNORECASE)
            table_name = table_alias.match(t) # create match object for each table
            if not table_name:
                raise ValueError(f"Cannot parse table in FROM clause: {t}")
            name, alias = table_name.groups() # extract name and alias from the match
            alias = alias or name
            from_clause["tables"][alias] = name # add to tables dict
        # print(f"FROM clause parsed (cartesian products): {from_clause}")  # DEBUG
        return from_clause


    # Regex to match first table: "TableName Alias"
    first_table_regex = re.compile(r"(\w+)(?:\s+(\w+))?", re.IGNORECASE)
    m = first_table_regex.match(statement) # create match object for first table
    if not m:
        raise ValueError("Cannot parse first table in FROM clause")
    
    table_name, alias = m.groups() # extract table name and alias from the match
    alias = alias or table_name # if no alias, use table name
    from_clause["tables"][alias] = table_name # add to tables dict
    last_alias = alias # keep track of last alias for joins
    
    # Remove the matched first table from statement
    statement = statement[m.end():].strip()
    
    
    # Regex to match JOINs
    join_regex = re.compile(
        r"(INNER|LEFT OUTER|LEFT|RIGHT|FULL OUTER)?\s*JOIN\s+(\w+)\s+(\w+)\s+ON\s+([^ ]+(?:\s*=\s*[^ ]+)*)",
        re.IGNORECASE
    )
    
    while statement: # iteratively parse joins
        jm = join_regex.match(statement) # create match object for join
        if not jm: # if there is no join match, theres no joins
            break  # no more joins
        
        join_type, right_table, right_alias, condition = jm.groups() # extract join info from match
        join_type = (join_type or "JOIN").upper() # default to JOIN if no type specified
        
        from_clause["tables"][right_alias] = right_table # add right table to tables dict
        # add join info as dict to joins list
        from_clause["joins"].append({
            "type": join_type,
            "left_table": last_alias,
            "right_table": right_alias,
            "condition": condition.strip()
        })
        
        last_alias = right_alias
        statement = statement[jm.end():].strip() # remove matched join from statement
    # print(f"FROM clause parsed: {from_clause}")  # DEBUG
    return from_clause

def parse_where(statement):
    # Parse the WHERE clause into structured predicates.
    # Supports AND/OR, parentheses, and comparison operators.

    if not statement or not statement.strip(): # if empty, return empty list
        return []

    s = statement.strip() # remove leading/trailing whitespace

    operators = [
        r">=", r"<=", r"<>", r"!=", r"=", r">", r"<",
        r"LIKE", r"IN", r"BETWEEN", r"IS NOT", r"IS"
    ] # these are the list of possible opertors in SQL, not sure which all are used in the assignment
    operator_regex = "|".join(operators) # join operators with or for regex

    # match tokens: parentheses, AND/OR, comparisons
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

        g = m.groups() # get matched groups

        # Determine which group matched and create corresponding token
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

        idx = m.end() # move index to end of matched token

    # print("WHERE Parsed Tokens:", tokens)
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
        m = re.match(r"(.+?)\s+(ASC|DESC)$", part, re.IGNORECASE) # match expression with optional direction (ASC/DESC)
        if m:
            expr = m.group(1).strip() # extract expression
            direction = m.group(2).upper() # extract direction
        else:
            expr = part
            direction = "ASC" # SQL default

        results.append({ # add to results list
            "expr": expr,
            "direction": direction
        })

    print("ORDER BY Parsed:", results)
    return results


###############################################
################ TREE PRINTING ################
###############################################

def build_canonical(parsed_sql):
    # 1. Create TABLE nodes for all tables
    tables = parsed_sql.get("from", {}).get("tables", {})
    table_nodes = {alias: QueryNode("TABLE", {"name": name}) for alias, name in tables.items()}


    # 2. Build JOIN nodes if any joins present
    joins = parsed_sql.get("from", {}).get("joins", [])
    if not joins:
        # No joins, just one table node or cartesian product
        if len(table_nodes) == 1:
            root = next(iter(table_nodes.values()))
        else:
            # Simple cartesian product JOIN all tables left to right
            table_list = list(table_nodes.values())
            root = table_list[0]
            for tnode in table_list[1:]:
                root = QueryNode("JOIN", {"condition": None, "type": "CROSS JOIN"}, [root, tnode])
    else:
        # Build join tree left to right based on join info
        # Start with the left table of first join
        first_join = joins[0]
        left_alias = first_join["left_table"]
        right_alias = first_join["right_table"]
        left_node = table_nodes[left_alias]
        right_node = table_nodes[right_alias]
        root = QueryNode("JOIN", {
            "condition": first_join["condition"],
            "type": first_join["type"]
        }, [left_node, right_node])

        # For subsequent joins, attach as right child
        for join in joins[1:]:
            right_alias = join["right_table"]
            right_node = table_nodes[right_alias]
            root = QueryNode("JOIN", {
                "condition": join["condition"],
                "type": join["type"]
            }, [root, right_node])


    # 3. Wrap WHERE clause as SELECT node if any condition
    where_tokens = parsed_sql.get("where", [])
    if where_tokens:
        cond_str = tokens_to_condition(where_tokens)
        root = QueryNode("SELECT", {"condition": cond_str}, [root])


    # 4. Group by clause 
    # get group_by_clause from parsed_sql
    group_by = parsed_sql.get("group by", [])
    
    # build one long clause to put in the details attribute of QueryNode (for good printing)
    if group_by:
        group_clause_together = ""
        for token in group_by:
            group_clause_together+=token
            group_clause_together+=" "
    
    if group_by:
        root = QueryNode("GROUP BY", group_clause_together, [root])   
        

    # 5. Having clause
    # get having_clause from parsed_sql
    having = parsed_sql.get("having", [])
    
    # build one long clause to put in the details attribute of QueryNode (for good printing)
    if having:
        having_clause_together = ""
        for token in having:
            having_clause_together+=token['left']
            having_clause_together+=" "
            having_clause_together+=token['operator']
            having_clause_together+=" "
            having_clause_together+=token['right']
    if having:
        root = QueryNode("HAVING", having_clause_together, [root])
    
    
    # 6. Wrap PROJECT node for SELECT projections
    select_proj = parsed_sql.get("select", {})
    proj_list = []
    for alias, attrs in select_proj.items():
        for attr in attrs:
            if alias == "*":
                proj_list.append(attr)
            else:
                proj_list.append(f"{alias}.{attr}")
    root = QueryNode("PROJECT", {"projections": proj_list}, [root])
    
    
    # 7. Order by clause
    order_by = parsed_sql.get("order by", [])
    
    # build one long clause to put in the details attribute of QueryNode (for good printing)
    if order_by:
        order_clause_together = ""
        for token in order_by:     # should only be one but still
            order_clause_together+=token['expr']
            order_clause_together+=" "
            order_clause_together+=token['direction']
            order_clause_together+=" "

    # update root node to be order by if there is one
    if order_by:
        root = QueryNode("ORDER BY", order_clause_together, [root])

    print("\n\nroot",root.children.pop,"\n\n")
    return root

#
#
#
#
def groupby_having_orderby(parsed_sql, root):
    # 6. Group by clause 
    # get group_by_clause from parsed_sql
    group_by = parsed_sql.get("group by", [])
    
    # build one long clause to put in the details attribute of QueryNode (for good printing)
    if group_by:
        group_clause_together = ""
        for token in group_by:
            group_clause_together+=token
            group_clause_together+=" "
    
    if group_by:
        root = QueryNode("GROUP BY", group_clause_together, [root])   
        

    # 7. Having clause
    # get having_clause from parsed_sql
    having = parsed_sql.get("having", [])
    
    # build one long clause to put in the details attribute of QueryNode (for good printing)
    if having:
        having_clause_together = ""
        for token in having:
            having_clause_together+=token['left']
            having_clause_together+=" "
            having_clause_together+=token['operator']
            having_clause_together+=" "
            having_clause_together+=token['right']
    # update root to having node if there is one
    if having:
        root = QueryNode("HAVING", having_clause_together, [root])
    
    
    # 8. add PROJECT node at top
    select_proj = parsed_sql.get("select", {})
    proj_list = []
    for alias, attrs in select_proj.items(): # this is already separated by table for later (push projections), so have to loop through all
        for attr in attrs:
            proj_list.append(f"{alias}.{attr}" if alias != "*" else attr) # add projections, if * just use *

    # update root to project node
    root = QueryNode("PROJECT", {"projections": proj_list}, [root]) # add projection node


     # 9. Order by clause
    order_by = parsed_sql.get("order by", [])
    
    # build one long clause to put in the details attribute of QueryNode (for good printing)
    if order_by:
        order_clause_together = ""
        for token in order_by:     # should only be one but still
            order_clause_together+=token['expr']
            order_clause_together+=" "
            order_clause_together+=token['direction']
            order_clause_together+=" "

    # update root node to be order by if there is one
    if order_by:
        root = QueryNode("ORDER BY", order_clause_together, [root])
    
    return root

###############################################
############### OPTIMIZATION ##################
###############################################

def optimized_step1(parsed_sql):
    # Push down all selections per table into a single SELECT node above table
    # If a selection clause has 2 tables, keep above join
    
    # 1. Create table nodes
    tables = parsed_sql.get("from", {}).get("tables", {})
    table_nodes = {alias: QueryNode("TABLE", {"name": name}) for alias, name in tables.items()}

    # 2. Split WHERE into single table and multi table
    where_tokens = parsed_sql.get("where") or [] # grab where (selection) dict
    single_table = []  # list of (table_alias, condition_str)
    multi_table = []   # list of condition_str

    for token in where_tokens: # parses each selection (where statement) i.e. E.Sex = 'M'
        if isinstance(token, dict): # checks if token is a dictionary so it doesn't error out
            tables_in_cond = set() 
            for side in [token['left'], token['right']]:
                if '.' in side: # checks if side of condition has a table
                    tables_in_cond.add(side.split('.')[0]) # get table alias
            condition_str = f"{token['left']} {token['operator']} {token['right']}" # get full condition string (i.e. E.Sex = 'M')

            if len(tables_in_cond) == 1: # checks how many tables are in condition
                single_table.append((tables_in_cond.pop(), condition_str)) # if one table, push selection all the way down to table
            else: 
                multi_table.append(condition_str) # if multiple tables, it cannot be pushed below the join

    # 3. Create single table condition nodes
    table_nodes_wrapped = {} 
    for alias, node in table_nodes.items(): # for each row in the dict
        conds = [c for a, c in single_table if a == alias] # get all conditions (selections for this table)
        if conds:
            combined = " AND ".join(conds) # if multiple conditions, insert AND
            node = QueryNode("SELECT", {"condition": combined}, [node]) # create a new node above the table with selections
        table_nodes_wrapped[alias] = node # table node + select conditions

    # 4. Build JOIN tree
    joins = parsed_sql.get("from", {}).get("joins", []) # grab join dict
    if not joins: # if there are no Inner/outer joints, create cross joins
        table_list = list(table_nodes_wrapped.values())
        if len(table_list) == 1: # if only 1 table, don't need to join
            root = table_list[0]
        else:
            root = table_list[0]
            for tnode in table_list[1:]:
                root = QueryNode("JOIN", {"condition": None, "type": "CROSS JOIN"}, [root, tnode]) # Create a cross join node
    else: # if joins already exist (inner/outer)
        first_join = joins[0]
        left_node = table_nodes_wrapped[first_join["left_table"]] # get left table
        right_node = table_nodes_wrapped[first_join["right_table"]] # get right table
        root = QueryNode("JOIN", {"condition": first_join["condition"], "type": first_join["type"]}, [left_node, right_node]) # create join node

        for join in joins[1:]: # handles joins with already joined tables (i.e. if you have 3 tables - (A+B)+C )
            right_node = table_nodes_wrapped[join["right_table"]]
            root = QueryNode("JOIN", {"condition": join["condition"], "type": join["type"]}, [root, right_node])

    # 5. multi table condition above joins
    if multi_table:
        combined_multi = " AND ".join(multi_table) # if multiple conditions, insert AND
        root = QueryNode("SELECT", {"condition": combined_multi}, [root])


    return groupby_having_orderby(parsed_sql, root)


def handle_selections(parsed_sql):
    # 1. Create table nodes
    tables = parsed_sql.get("from", {}).get("tables", {})
    table_nodes = {alias: QueryNode("TABLE", {"name": name}) for alias, name in tables.items()}


    # 2. Split WHERE into single table and multi table
    where_tokens = parsed_sql.get("where") or []
    single_table = []  # list of (table_alias, condition_dict)
    multi_table = []   # list of condition_dict

    for token in where_tokens: # parses each selection (where statement) i.e. E.Sex = 'M'
        if isinstance(token, dict): # checks if token is a dictionary so it doesn't error out
            tables_in_cond = set()
            for side in [token['left'], token['right']]:
                if '.' in side: # checks if side of condition has a table
                    tables_in_cond.add(side.split('.')[0]) # get table alias
            condition_str = f"{token['left']} {token['operator']} {token['right']}" # get full condition string (i.e. E.Sex = 'M')
            cond_info = {"condition": condition_str, "operator": token['operator']} # get operator for ordering of selections

            if len(tables_in_cond) == 1: # checks how many tables are in condition
                single_table.append((tables_in_cond.pop(), cond_info)) # if one table, push selection all the way down to table
            else: 
                multi_table.append(cond_info) # if multiple tables, it cannot be pushed below the join


    # 3. handle table nodes with high/low selectivity for single table conditions
    table_nodes_wrapped = {}
    for alias, node in table_nodes.items():
        conds = [c for a, c in single_table if a == alias] # Get all conditions
        if not conds:
            table_nodes_wrapped[alias] = node
            continue

        high_sel = [c['condition'] for c in conds if c['operator'] == '='] # if operator is =, should be closer to table
        low_sel = [c['condition'] for c in conds if c['operator'] != '='] # otherwise, needs to be higher in tree

        current_node = node
        if high_sel:
            current_node = QueryNode("SELECT", {"condition": " AND ".join(high_sel)}, [current_node]) # adds higher selectivity node first
        if low_sel:
            current_node = QueryNode("SELECT", {"condition": " AND ".join(low_sel)}, [current_node]) # add low selectivity higher in tree

        table_nodes_wrapped[alias] = current_node
    return table_nodes_wrapped, multi_table

def optimized_step2(parsed_sql):
    # Push down selections by selectivity:
    # Single table:
    #   High selectivity (=) closest to table
    #   Low selectivity (<, >, <=, >=, !=, <>) on top
    # Multi table: stay above joins
    
    # 1. Create table nodes, split selections, handle selectivity
    table_nodes_wrapped, multi_table = handle_selections(parsed_sql)

    # 2. Build JOIN tree
    joins = parsed_sql.get("from", {}).get("joins", []) # grab join dict
    if not joins: # if there are no Inner/outer joints, create cross joins
        table_list = list(table_nodes_wrapped.values())
        if len(table_list) == 1: # if only 1 table, don't need to join
            root = table_list[0]
        else:
            root = table_list[0]
            for tnode in table_list[1:]:
                root = QueryNode("JOIN", {"condition": None, "type": "CROSS JOIN"}, [root, tnode]) # Create a cross join node
    else: # if joins already exist (inner/outer)
        first_join = joins[0]
        left_node = table_nodes_wrapped[first_join["left_table"]] # get left table
        right_node = table_nodes_wrapped[first_join["right_table"]] # get right table
        root = QueryNode("JOIN", {"condition": first_join["condition"], "type": first_join["type"]}, [left_node, right_node]) # create join node

        for join in joins[1:]: # handles joins with already joined tables (i.e. if you have 3 tables - (A+B)+C )
            right_node = table_nodes_wrapped[join["right_table"]]
            root = QueryNode("JOIN", {"condition": join["condition"], "type": join["type"]}, [root, right_node])

    # 3. multi table condition above joins
    if multi_table:
        cond_str = " AND ".join(c["condition"] for c in multi_table) #include condition
        root = QueryNode("SELECT", {"condition": cond_str}, [root])
        
    return groupby_having_orderby(parsed_sql, root)


def optimized_step3(parsed_sql):
    # Replace cartesian products + selections with joins

    # 1. Create table nodes, split selections, handle selectivity
    table_nodes_wrapped, multi_table = handle_selections(parsed_sql)

    # 2. Build JOIN tree
    joins = parsed_sql.get("from", {}).get("joins", []) # grab join dict
    if not joins: # if there are no Inner/outer joints, create cross joins
        table_list = list(table_nodes_wrapped.values())

        # If only one table, nothing to join
        if len(table_list) == 1:
            root = table_list[0]
        else:
            # Build the CROSS JOIN chain
            root = table_list[0]
            for tnode in table_list[1:]:
                root = QueryNode(
                    "JOIN",
                    {"condition": None, "type": "CROSS JOIN"},
                    [root, tnode]
                )

        # convert CROSS JOIN to INNER JOIN if multi table condition is equijoin
        equi_join_preds = []
        leftover_select_preds = []

        for cond in multi_table:
            condition_str = cond["condition"]
            op = cond["operator"]

            # extract left and right sides
            left, right = condition_str.split(f" {op} ")

            # check if operator is = and both sides use a table
            if op == "=" and "." in left and "." in right:
                equi_join_preds.append(condition_str)
            else:
                leftover_select_preds.append(condition_str)

        # If equi-join predicates found, rewrite root join
        if equi_join_preds:
            root.details["type"] = "INNER JOIN"
            root.details["condition"] = " AND ".join(equi_join_preds)

        # keep only leftover predicates for the SELECT above join
        multi_table = [{"condition": p} for p in leftover_select_preds]
    else: # if joins already exist (inner/outer)
        first_join = joins[0]
        left_node = table_nodes_wrapped[first_join["left_table"]] # get left table
        right_node = table_nodes_wrapped[first_join["right_table"]] # get right table
        root = QueryNode("JOIN", {"condition": first_join["condition"], "type": first_join["type"]}, [left_node, right_node]) # create join node

        for join in joins[1:]: # handles joins with already joined tables (i.e. if you have 3 tables - (A+B)+C )
            right_node = table_nodes_wrapped[join["right_table"]]
            root = QueryNode("JOIN", {"condition": join["condition"], "type": join["type"]}, [root, right_node])


    # 3. multi table condition above joins
    if multi_table:
        cond_str = " AND ".join(c["condition"] for c in multi_table) #include condition
        root = QueryNode("SELECT", {"condition": cond_str}, [root])

    return groupby_having_orderby(parsed_sql, root)



def optimized_step4(parsed_sql):
    # Push down projections to tables based on needed attributes

    # If selecting all, use previous logic without projection pushdown
    select_proj = parsed_sql.get("select", {})
    is_select_all = ("*" in select_proj and len(select_proj.get("*", [])) == 1)
    if is_select_all:
        return optimized_step3(parsed_sql)

   
    table_nodes_wrapped, multi_table = handle_selections(parsed_sql)
    tables = parsed_sql.get("from", {}).get("tables", {})

    # Build JOIN tree
    joins = parsed_sql.get("from", {}).get("joins", [])
    table_list = list(table_nodes_wrapped.values())

    if not joins:
        if len(table_list) == 1:
            root = table_list[0]
        else:
            root = table_list[0]
            for tnode in table_list[1:]:
                root = QueryNode(
                    "JOIN",
                    {"condition": None, "type": "CROSS JOIN"},
                    [root, tnode]
                )

        # Convert CROSS JOIN to INNER JOIN when possible
        equi, leftover = [], []
        for cond in multi_table:
            text = cond["condition"]
            op = cond["operator"]
            left, right = text.split(f" {op} ")
            if op == "=" and "." in left and "." in right:
                equi.append(text)
            else:
                leftover.append(text)

        if equi:
            root.details["type"] = "INNER JOIN"
            root.details["condition"] = " AND ".join(equi)

        multi_table = [{"condition": c} for c in leftover]

    else:
        j = joins[0]
        left = table_nodes_wrapped[j["left_table"]]
        right = table_nodes_wrapped[j["right_table"]]
        root = QueryNode("JOIN", {"condition": j["condition"], "type": j["type"]}, [left, right])
        for j in joins[1:]:
            right = table_nodes_wrapped[j["right_table"]]
            root = QueryNode("JOIN", {"condition": j["condition"], "type": j["type"]}, [root, right])

    # multi table condition above joins
    if multi_table:
        cond_str = " AND ".join(c["condition"] for c in multi_table)
        root = QueryNode("SELECT", {"condition": cond_str}, [root])

    # 3. get needed attributes per table
    needed = {alias: set() for alias in tables.keys()}

    # get attributes from SELECT statment
    for alias, attrs in select_proj.items():
        if alias != "*":
            for a in attrs:
                needed[alias].add(f"{alias}.{a}")

    # extract attributes in join conditions
    def attrs_from_cond(cond):
        if not cond:
            return []
        parts = cond.replace("=", " ").replace("<", " ").replace(">", " ").split() # split on operators
        return [p for p in parts if "." in p] # return only parts with table.attribute

    def collect_join_attrs(node): # recursively collect join attributes
        if node.node_type == "JOIN":
            attrs = attrs_from_cond(node.details.get("condition")) # get attributes from join condition
            for a in attrs:
                alias = a.split(".")[0] # get table alias
                if alias in needed: # check if alias is valid
                    needed[alias].add(a) # add to needed set

            collect_join_attrs(node.children[0]) # recurse leftward down tree
            collect_join_attrs(node.children[1]) # recurse rightward down tree

    collect_join_attrs(root) # start collecting from root


    def attach_projects(node):
        # If this node is TABLE or SELECT whose child is TABLE, insert PROJECT above subtree
        if node.node_type == "TABLE":
            alias = None
            for a, tname in tables.items(): # find alias for table
                if tname == node.details["name"]: # Matches table name to child table
                    alias = a
                    break # stop loop once found
            proj_list = sorted(needed[alias]) # get needed attributes for this table
            return QueryNode("PROJECT", {"projections": proj_list}, [node]) # build project node above table

        if node.node_type == "SELECT" and node.children[0].node_type == "TABLE": # if select node is above table node need to insert project above select
            child = node.children[0] # get table
            alias = None
            for a, tname in tables.items(): # find alias for table
                if tname == child.details["name"]: # Matches table name to child table
                    alias = a
                    break # stop loop once found

            proj_list = sorted(needed[alias]) # get needed attributes for this table
           
            return QueryNode("PROJECT", {"projections": proj_list}, [QueryNode("SELECT", node.details, [child])]) # build project node above selection its child table node

        # JOIN: recurse both sides
        if node.node_type == "JOIN":
            left = attach_projects(node.children[0]) # recurse left child
            right = attach_projects(node.children[1]) # recurse right child
            return QueryNode("JOIN", node.details, [left, right]) # rebuild join with new children

        # Higher nodes (GROUP BY, HAVING, etc): recurse single child
        if node.children: # if node has children
            node.children = [attach_projects(node.children[0])] # recurse single child
        return node

    root = attach_projects(root) # attach projects recursively

    return groupby_having_orderby(parsed_sql, root)




def tokens_to_condition(tokens):
    result = []
    for token in tokens:
        if isinstance(token, str):
            result.append(token)
        else:
            # token is dict: {"left": ..., "operator": ..., "right": ...}
            result.append(f"{token['left']} {token['operator']} {token['right']}")
    return " ".join(result)

def print_query_tree(node, indent=0):
    print("  " * indent + f"{node.node_type}: {node.details}")
    for child in node.children:
        print_query_tree(child, indent + 1)

class QueryNode:
    def __init__(self, node_type, details=None, children=None):
        self.node_type = node_type              # e.g., "TABLE", "JOIN", "SELECT", "PROJECT"
        self.details = details or {}            # dictionary of node-specific info
        self.children = children or []          # list of child QueryNodes

    def __repr__(self):
        return f"{self.node_type}({self.details})"
    

def build_graph(node, graph=None, parent=None):
    if graph is None:
        graph = Digraph(comment="Query Plan")
    
    # Give each node a unique ID
    node_id = str(id(node))
    
    # Label the node
    if node.node_type == "PROJECT":
        label = f"PROJECT\n{', '.join(node.details.get('projections', []))}"
    elif node.node_type == "SELECT":
        label = f"SELECT\n{node.details.get('condition','')}"
    elif node.node_type == "JOIN":
        label = f"{node.details.get('type','JOIN')}\n{node.details.get('condition','')}"
    elif node.node_type == "GROUP BY":    
        label = f"GROUP BY\n{node.details}"  # TODO: fix formatting so there arent brackets in output
    elif node.node_type == "HAVING":
        label = f"HAVING\n{node.details}" # TODO: fix formatting
    elif node.node_type == "ORDER BY":
        label = f"ORDER BY\n{node.details}"  # TODO: fix formatting
    else:
        label = f"{node.node_type}\n{node.details.get('name','')}"   # this is the part that messes up when i add the group by clause
    
    graph.node(node_id, label)
    
    if parent:
        graph.edge(parent, node_id)
    
    for child in node.children:
        build_graph(child, graph, node_id)
    
    return graph

'''

1. Push down selections (rule 1 & 2)
2. small selectivity first - equal before range (rule 3)
3. Replace cartesian product and selection with join (rule 4)
4. Push projections down (rule 5)

'''




# main driver function
if __name__ == "__main__":
    input_file = "input.txt"

    render_images = False

    parsed_sql = parse_sql_txt(input_file)
    if parsed_sql:
        
        print("Canonical tree generated as 'canonical.png'\n\n")
        query_tree = build_canonical(parsed_sql)
        initial_graph = build_graph(query_tree)
        initial_graph.render("canonical", view=render_images, format="png")

        
        # 1. Push down selections (rule 1 & 2)
        print("Step 1. Push down selections")
        print("\tIdentified conjunctive selections, broke them up individually,\n\tand pushed them down as far as possible.")
        print("\tSelections involving multiple tables were kept above joins.\n")
        print("Step 1 tree generated as 'step1.png'\n\n")
        step1 = optimized_step1(parsed_sql)
        step1_tree = build_graph(step1)
        step1_tree.render("step1", view=render_images, format="png")

        
        # 2. small selectivity first - equal before range (rule 3)
        print("Step 2. Reorder selections by selectivity")
        print("\tSelections with high selectivity (equality conditions) were pushed\n\tcloser to the table, while low selectivity (range conditions) were placed higher.\n")
        print("Step 2 tree generated as 'step2.png'\n\n")
        step2 = optimized_step2(parsed_sql)
        step2_tree = build_graph(step2)
        step2_tree.render("step2", view=render_images, format="png")

        # 3. Replace cartesian product and selection with join (rule 4)
        print("Step 3. Replace cartesian products with joins")
        print("\tCROSS JOINs followed by selection conditions that could be\n\tconverted into equi joins were replaced with INNER JOINs.\n")
        print("Step 3 tree generated as 'step3.png'\n\n")
        step3 = optimized_step3(parsed_sql)
        step3_tree = build_graph(step3)
        step3_tree.render("step3", view=render_images, format="png")


        # 4. Push projections down (rule 5)
        print("Step 4. Push down projections")
        print("\tProjections were pushed down to the lowest possible points in the tree,\n\tbased on the attributes needed for higher operations.\n")
        print("Step 4 tree generated as 'step4.png'\n\n")
        step4 = optimized_step4(parsed_sql)
        step4_tree = build_graph(step4)
        step4_tree.render("step4", view=render_images, format="png")

        
