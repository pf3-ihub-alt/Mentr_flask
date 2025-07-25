from pymongo import MongoClient
from rank import ProductManager, rank_pm, generate_feedback

# MongoDB connection string
MONGO_URI = "mongodb+srv://nithishgihub:6Ehv1X8OCa2Rtgyl@cluster0.jnj2s.mongodb.net/yourDatabaseName?retryWrites=true&w=majority"

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client['yourDatabaseName']  # Replace 'yourDatabaseName' with your actual database name

def fetch_new_startups():
    # Fetch startups that are not yet in project_details
    existing_startup_ids = db.project_details.distinct("startup_id")
    return db.startup_details.find({"_id": {"$nin": existing_startup_ids}}).sort('created_at', -1)

def fetch_product_managers():
    product_managers_data = db.product_managers.find()
    product_managers = []
    
    for pm_data in product_managers_data:
        pm = ProductManager(
            name=pm_data['name'],
            industry_priorities=pm_data.get('industry_verticals', []),
            tech_priorities=pm_data.get('technology_stack', []),
            project_status_priorities=pm_data.get('project_status', []),
            experience=int(pm_data.get('years_experience', 0)),
            performance_score=int(pm_data.get('performance_score', 0)),
            current_workload=int(pm_data.get('active_projects', 0))
        )
        # Attach the MongoDB _id to the ProductManager instance
        pm.mongo_id = pm_data['_id']
        product_managers.append(pm)
    
    return product_managers

def allot_projects():
    startups = fetch_new_startups()
    product_managers = fetch_product_managers()

    for startup in startups:
        # Extract necessary startup details
        startup_id = str(startup['_id'])
        
        # Check if this startup_id is already in project_details
        if db.project_details.find_one({"startup_id": startup_id}):
            continue  # Skip this startup if it already exists in project_details
        
        problem_statement = startup['problem_statement']
        tech_stack = startup.get('industry_technology', [])  # Assuming this is a list
        industry_vertical = startup.get('industry_vertical', '')
        project_status = startup.get('current_status', '')

        # Rank the PMs based on the startup details
        ranked_pms = rank_pm(product_managers, tech_stack, industry_vertical, project_status)
        
        if not ranked_pms:
            print(f"No suitable Product Manager found for startup {startup_id}")
            continue

        # Get the best PM and its ID
        best_pm_name = ranked_pms[0][4]
        best_pm = next(pm for pm in product_managers if pm.name == best_pm_name)
        best_pm_id = best_pm.mongo_id

        # Generate feedback
        feedback = generate_feedback(ranked_pms, tech_stack, industry_vertical, project_status)
        
        # Store the project allotment in the project_details collection
        project_details = {
            "startup_id": startup_id,
            "problem_statement": problem_statement,
            "tech_stack": tech_stack,
            "industry_vertical": industry_vertical,
            "project_status": project_status,
            "assigned_pm": best_pm_name,
            "assigned_pm_id": str(best_pm_id),  # Store the PM ID here
            "pm_ranking": [{"name": pm[4], "id": next(p.mongo_id for p in product_managers if p.name == pm[4])} for pm in ranked_pms],  # Storing the PM ranking order with IDs
            "Feedback": feedback
        }

        db.project_details.insert_one(project_details)

