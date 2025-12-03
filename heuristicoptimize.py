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
        print(sql_txt_remove_line)
        # Split the content by semicolon and SQL operation keywords
        # Extracts each part of the SQL statement (excluding the keyword)
        #
        # The regex is a pain to read, but it basically looks for the keyword that starts an operation
        # it then captures everything after the keyword until hitting another keyword or ;
        # then passes that to the respective parser function
        select_clause = re.search(r"SELECT\s+(.*?)\s+FROM", sql_txt_remove_line, re.IGNORECASE)
        print(f"Select Clause: {select_clause.group(1)}") #testing
        select_parsed = parse_select(select_clause.group(1))
        from_clause = re.search(r"FROM\s+(.*?)(?=\s+WHERE|\s+GROUP BY|\s+HAVING|\s+ORDER BY|\s*;|$)", sql_txt_remove_line, re.IGNORECASE)
        print(f"From Clause: {from_clause.group(1)}") #testing
        from_parsed = parse_from(from_clause.group(1))
        where_clause = re.search(r"WHERE\s+(.*?)\s+(GROUP BY|;)", sql_txt_remove_line, re.IGNORECASE)
        where_parsed = None
        if where_clause:
            print(f"Where Clause: {where_clause.group(1)}") #testing
            where_parsed = parse_where(where_clause.group(1))
        group_by_clause = re.search(r"GROUP BY\s+(.*?)\s+(HAVING|;)", sql_txt_remove_line, re.IGNORECASE)
        group_by_parsed = None
        if group_by_clause:
            print(f"Group By Clause: {group_by_clause.group(1)}") #testing
            group_by_parsed = parse_group_by(group_by_clause.group(1))
        having_clause = re.search(r"HAVING\s+(.*?)\s+(ORDER BY|;)", sql_txt_remove_line, re.IGNORECASE)
        having_parsed = None
        if having_clause:
            print(f"Having Clause: {having_clause.group(1)}") #testing
            having_parsed = parse_having(having_clause.group(1))
        order_by_clause = re.search(r"ORDER BY\s+(.*?);", sql_txt_remove_line, re.IGNORECASE)
        order_by_parsed = None
        if order_by_clause:
            print(f"Order By Clause: {order_by_clause.group(1)}") #testing
            order_by_parsed = parse_order_by(order_by_clause.group(1))

        return {
            "select": select_parsed, 
            "from": from_parsed, 
            "where": where_parsed, 
            "group by": group_by_parsed, 
            "having": having_parsed, 
            "order by": order_by_parsed
        }

        

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


# parse from clause which gives tables and joins
def parse_from(statement):
    # parses FROM clause to extract tables and joins
    # first checks if it is a cartesian product (comma separated tables)
    # if not, parses joins iteratively and checks join type
    # produces a dict with "tables" and "joins" keys.
    # Join values are dicts with type, left_table, right_table, condition

    # init dictionary for tables and joins
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


################ TREE PRINTING
def build_query_tree(parsed_sql):
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
    if group_by:
        root = QueryNode("GROUP BY", group_by, [root])
        
    # 5. having clause
    # get having_clause from parsed_sql
    having = parsed_sql.get("having", [])
    if having:
        root = QueryNode("HAVING", having, [root])
    
    # 6. Wrap PROJECT node for SELECT projections
    select_proj = parsed_sql.get("select", {})
    proj_list = []
    for alias, attrs in select_proj.items():
        for attr in attrs:
            if alias == "*":
                proj_list.append(attr)
            else:
                proj_list.append(f"{alias}.{attr}")
                
    # 7. Build Order by node  
    order_by = parsed_sql.get("order by", [])
    if order_by:
        root = QueryNode("ORDER BY", order_by, [root])
    
        
    

    root = QueryNode("PROJECT", {"projections": proj_list}, [root])

    return root

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
    else:
        label = f"{node.node_type}\n{node.details.get('name','')}"
    
    graph.node(node_id, label)
    
    if parent:
        graph.edge(parent, node_id)
    
    for child in node.children:
        build_graph(child, graph, node_id)
    
    return graph

# main driver function
if __name__ == "__main__":
    input_file = "input3.txt"
    parsed_sql = parse_sql_txt(input_file)
    if parsed_sql:
        # build canonical tree
        query_tree = build_query_tree(parsed_sql)
        
        # build canonical tree graph
        initial_graph = build_graph(query_tree)
        
        # render canonical tree graph as png
        initial_graph.render("query_plan_tree", view=True, format="png")
        
        # OPTIMIZATION
        # step 1: break up selections
        # build tree           
        optimize_step1(parsed_sql);
        # build graph
        # render graph as png
         
        # step 2: push down selections
        # build tree
        # build graph
        # render graph as png
        
        # step 3: sort selections by selectivity
        # build tree
        # build graph
        # render graph as png
        
        # step 4: replace cross join + selection with equi-join
        # build tree
        # build graph
        # render graph as png
        
        # step 5: push projections down
        # build tree
        # build graph
        # render graph as png
