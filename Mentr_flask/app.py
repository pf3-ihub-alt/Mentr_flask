from flask import Flask, render_template, redirect, url_for, request, flash, make_response
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from bson.objectid import ObjectId
from allot import allot_projects
import os,jsonify,datetime
from flask import Flask, jsonify, request
from rank import rank_pm

app = Flask(__name__)
app.secret_key = os.urandom(24)

# MongoDB configuration
app.config["MONGO_URI"] = "mongodb+srv://nithishgihub:6Ehv1X8OCa2Rtgyl@cluster0.jnj2s.mongodb.net/yourDatabaseName?retryWrites=true&w=majority"
mongo = PyMongo(app)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Product Manager Model
class ProductManager(UserMixin):
    def __init__(self, name, email, password, years_experience, performance_score, active_projects, industry_verticals, technology_stack, project_status, _id=None):
        self.id = _id
        self.name = name
        self.email = email
        self.password = password
        self.years_experience = years_experience
        self.performance_score = performance_score
        self.active_projects = active_projects
        self.industry_verticals = industry_verticals
        self.technology_stack = technology_stack
        self.project_status = project_status


@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.product_managers.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return ProductManager(
            name=user_data.get('name'),
            email=user_data.get('email'),
            password=user_data.get('password'),
            years_experience=user_data.get('years_experience'),
            performance_score=user_data.get('performance_score'),
            active_projects=user_data.get('active_projects'),
            industry_verticals=user_data.get('industry_verticals'),
            technology_stack=user_data.get('technology_stack'),
            project_status=user_data.get('project_status'),
            _id=user_id
        )
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.form

        years_experience = data.get('experience')  # Use .get() to avoid KeyError
        if not years_experience:
            flash('Years of experience is required', 'danger')
            return redirect(url_for('signup'))

        # Continue with other fields and processing
        industry_verticals = [data.get(f'industry_verticals_{i}') for i in range(1, 9) if data.get(f'industry_verticals_{i}')]
        technology_stack = [data.get(f'technologies_{i}') for i in range(1, 8) if data.get(f'technologies_{i}')]
        project_status = [data.get(f'project_statuses_{i}') for i in range(1, 5) if data.get(f'project_statuses_{i}')]

        product_manager = {
            'name': data.get('name'),
            'email': data.get('email'),
            'password': bcrypt.generate_password_hash(data.get('password')).decode('utf-8'),
            'years_experience': years_experience,
            'performance_score': data.get('performance_score'),
            'active_projects': data.get('active_projects'),
            'industry_verticals': industry_verticals,
            'technology_stack': technology_stack,
            'project_status': project_status
        }

        try:
            mongo.db.product_managers.insert_one(product_manager)
            flash('Signup successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error occurred: {e}', 'danger')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        user = mongo.db.product_managers.find_one({"email": data['email']})
        if user and bcrypt.check_password_hash(user['password'], data['password']):
            login_user(ProductManager(
                name=user['name'],
                email=user['email'],
                password=user['password'],
                years_experience=user['years_experience'],
                performance_score=user['performance_score'],
                active_projects=user['active_projects'],
                industry_verticals=user['industry_verticals'],
                technology_stack=user['technology_stack'],
                project_status=user['project_status'],
                _id=str(user['_id'])
            ))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get the current PM's user ID from the database
        pm = mongo.db.product_managers.find_one({"name": current_user.name}, {"_id": 1})
        if not pm:
            return jsonify({"message": "PM not found"}), 404

        pm_id = str(pm['_id'])  # Convert ObjectId to string since assigned_pm_id is a string

        # Step 1: Retrieve existing ideas, interested, shortlisted, and finalized if pm_id already exists in pm_slots
        pm_slot = mongo.db.pm_slots.find_one({"pm_id": pm_id}, {"ideas": 1, "interested": 1, "shortlisted": 1, "finalized": 1})

        # Initialize the set of existing project IDs in 'ideas'
        existing_project_ids = set(pm_slot['ideas']) if pm_slot and 'ideas' in pm_slot else set()

        # Also initialize sets for interested, shortlisted, and finalized
        interested_project_ids = set(pm_slot['interested']) if pm_slot and 'interested' in pm_slot else set()
        shortlisted_project_ids = set(pm_slot['shortlisted']) if pm_slot and 'shortlisted' in pm_slot else set()
        finalized_project_ids = set(pm_slot['finalized']) if pm_slot and 'finalized' in pm_slot else set()

        # Query project_details to find all projects assigned to the current PM
        assigned_projects = mongo.db.project_details.find({"assigned_pm_id": pm_id})

        # Create a list to store new project IDs as strings
        new_project_ids = []

        # Iterate through the assigned projects
        for project in assigned_projects:
            project_id_str = str(project['_id'])  # Convert ObjectId to string

            # Check if the project is not already in ideas, interested, shortlisted, or finalized
            if (project_id_str not in existing_project_ids and
                    project_id_str not in interested_project_ids and
                    project_id_str not in shortlisted_project_ids and
                    project_id_str not in finalized_project_ids):
                new_project_ids.append(project_id_str)

        # Combine existing and new project IDs and remove duplicates by converting to a set
        combined_project_ids = list(existing_project_ids.union(new_project_ids))

        # Update the pm_slots collection with the unique project IDs for 'ideas'
        mongo.db.pm_slots.update_one(
            {'pm_id': pm_id},  # Match based on pm_id as a string
            {'$set': {'ideas': combined_project_ids}},  # Set the ideas array with unique project IDs
            upsert=True
        )

        # Step 2: Retrieve and Display Startup Details Based on the updated `ideas` array

        # Fetch the updated `pm_slots` document for the current PM
        pm_slot = mongo.db.pm_slots.find_one({"pm_id": pm_id}, {"ideas": 1})

        # Initialize the list to store projects with corresponding startup details
        projects_with_startup_details = []

        # Check if 'ideas' array is not empty
        if pm_slot and "ideas" in pm_slot and pm_slot["ideas"]:
            # There are projects in the 'ideas' array, so fetch and display those projects
            for project_id in pm_slot['ideas']:
                # Convert project_id back to ObjectId and fetch project details
                project = mongo.db.project_details.find_one({"_id": ObjectId(project_id)})

                if project:
                    # Get the startup_id from the project
                    startup_id = project.get('startup_id')

                    # Fetch the corresponding startup details using the startup_id
                    startup_details = mongo.db.startup_details.find_one({"_id": ObjectId(startup_id)})

                    if startup_details:
                        # Append project and startup details to the list
                        projects_with_startup_details.append({
                            "project": project,
                            "startup_details": startup_details
                        })

            # Render the dashboard with the user's projects that are still in the 'Ideas' stage
            return render_template('dashboard.html', user=current_user, projects=projects_with_startup_details)

        else:
            # No projects in 'ideas', display a message or handle the empty case
            return render_template('dashboard.html', user=current_user, projects=[], message="No projects in your 'Ideas' stage.")

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'An error occurred on the server'}), 500





@app.route('/interested', methods=['POST'])
@login_required
def mark_interested():
    try:
        # Get the project_id from the JSON request
        data = request.get_json()
        project_id = data.get('project_id')

        if not project_id:
            return jsonify({'message': 'No project ID provided.'}), 400

        # Ensure project_id is a string
        if not isinstance(project_id, str):
            project_id = str(project_id)

        # Get the current PM's ID
        pm_id = current_user.id

        # Find the PM's slots
        pm_slots = mongo.db.pm_slots.find_one({'pm_id': pm_id})

        if pm_slots:
            # Get the 'ideas' and 'interested' arrays
            ideas = pm_slots.get('ideas', [])
            interested = pm_slots.get('interested', [])

            # Debugging: Print the current state
            print(f"Current ideas: {ideas}")
            print(f"Current interested: {interested}")

            # Check if the project_id is in the ideas array and remove it
            if project_id in ideas:
                ideas.remove(project_id)
                print(f"Removed {project_id} from ideas.")

            # Add the project_id to the interested array if it's not already there
            if project_id not in interested:
                interested.append(project_id)
                print(f"Added {project_id} to interested.")

                # Update the document with the new arrays
                result = mongo.db.pm_slots.update_one(
                    {'pm_id': pm_id},
                    {'$set': {'ideas': ideas, 'interested': interested}}
                )

                # Check if the update was successful
                if result.modified_count > 0 or result.upserted_id:
                    message = "Project has been moved to interested."
                else:
                    message = "Failed to update pm_slots document."
            else:
                message = "Project is already in the interested list."
        else:
            # If pm_slots doesn't exist, create it with the new interested project
            mongo.db.pm_slots.insert_one({
                'pm_id': pm_id,
                'ideas': [],
                'interested': [project_id]
            })
            message = "Project has been marked as interested."

        return jsonify({'message': message}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Log the error to the console
        return jsonify({'message': f'Error marking project as interested: {str(e)}'}), 500








@app.route('/interested_startups')
@login_required
def interested_startups_page():
    pm_id = current_user.id
    pm_slots = mongo.db.pm_slots.find_one({'pm_id': pm_id})
    interested_project_ids = pm_slots.get('interested', []) if pm_slots else []

    interested_projects = []
    for project_id in interested_project_ids:
        project = mongo.db.project_details.find_one({'_id': ObjectId(project_id)})
        if project:
            startup = mongo.db.startup_details.find_one({'_id': ObjectId(project['startup_id'])})
            interested_projects.append({
                'project': project,
                'startup_details': startup
            })

    return render_template('interested_startups.html', user=current_user, projects=interested_projects)


@app.route('/shortlist_startup', methods=['POST'])
@login_required
def shortlist_startup():
    project_id = request.form.get('project_id')

    # Find the project and update the PM's interested and shortlisted lists
    pm_id = current_user.id
    pm_slots = mongo.db.pm_slots.find_one({'pm_id': pm_id})

    if pm_slots:
        interested = pm_slots.get('interested', [])
        shortlisted = pm_slots.get('shortlisted', [])

        # Remove from interested array if it exists
        if project_id in interested:
            interested.remove(project_id)

        # Add to shortlisted array if it's not already there
        if project_id not in shortlisted:
            shortlisted.append(project_id)
            mongo.db.pm_slots.update_one({'pm_id': pm_id}, {'$set': {'shortlisted': shortlisted, 'interested': interested}})
            message = "Project has been moved to shortlisted."
        else:
            message = "Project is already in the shortlisted list."
    else:
        # If pm_slots doesn't exist, create it with the new shortlisted project
        mongo.db.pm_slots.insert_one({
            'pm_id': pm_id,
            'shortlisted': [project_id]
        })
        message = "Project has been shortlisted."

    return redirect(url_for('interested_startups_page'))



@app.route('/shortlisted_startups')
@login_required
def shortlisted_startups_page():
    pm_id = current_user.id
    pm_slots = mongo.db.pm_slots.find_one({'pm_id': pm_id})
    shortlisted_project_ids = pm_slots.get('shortlisted', []) if pm_slots else []

    shortlisted_projects = []
    for project_id in shortlisted_project_ids:
        project = mongo.db.project_details.find_one({'_id': ObjectId(project_id)})
        if project:
            startup = mongo.db.startup_details.find_one({'_id': ObjectId(project['startup_id'])})
            shortlisted_projects.append({
                'project': project,
                'startup_details': startup
            })

    return render_template('shortlisted_startups.html', user=current_user, projects=shortlisted_projects)

@app.route('/finalize_startup', methods=['POST'])
@login_required
def finalize_startup():
    try:
        project_id = request.form.get('project_id')

        # Find the PM's document
        pm_id = current_user.id
        pm_slots = mongo.db.pm_slots.find_one({'pm_id': pm_id})

        if pm_slots:
            shortlisted = pm_slots.get('shortlisted', [])
            finalized = pm_slots.get('finalized', [])

            # Remove from shortlisted array if it exists
            if project_id in shortlisted:
                shortlisted.remove(project_id)

            # Add to finalized array if it's not already there
            if project_id not in finalized:
                finalized.append(project_id)
                mongo.db.pm_slots.update_one({'pm_id': pm_id}, {'$set': {'shortlisted': shortlisted, 'finalized': finalized}})
                flash('Project has been finalized successfully!', 'success')
            else:
                flash('Project is already in the finalized list.', 'info')
        else:
            # If pm_slots doesn't exist, create it with the new finalized project
            mongo.db.pm_slots.insert_one({
                'pm_id': pm_id,
                'finalized': [project_id]
            })
            flash('Project has been finalized successfully!', 'success')

    except Exception as e:
        print(f"Error occurred: {e}")  # Log the error to the console
        flash('Error finalizing the project.', 'danger')

    return redirect(url_for('shortlisted_startups_page'))

@app.route('/finalized_startups')
@login_required
def finalized_startups_page():
    pm_id = current_user.id
    pm_slots = mongo.db.pm_slots.find_one({'pm_id': pm_id})
    finalized_project_ids = pm_slots.get('finalized', []) if pm_slots else []

    finalized_projects = []
    for project_id in finalized_project_ids:
        project = mongo.db.project_details.find_one({'_id': ObjectId(project_id)})
        if project:
            startup = mongo.db.startup_details.find_one({'_id': ObjectId(project['startup_id'])})
            finalized_projects.append({
                'project': project,
                'startup_details': startup
            })

    return render_template('finalized_startups.html', user=current_user, projects=finalized_projects)



def get_next_pm(pms, tech_stack, industry_vertical, project_status):
    try:
        ranked_pms = rank_pm(pms, tech_stack, industry_vertical, project_status)
        if ranked_pms:
            next_pm = ranked_pms[0][4]  # Ensure this is the correct field (e.g., name or ID)
            print(f"Next PM selected: {next_pm}")
            return next_pm
        print("No PMs ranked")
        return None
    except Exception as e:
        print(f'Error in get_next_pm: {e}')
        return None




@app.route('/send-to-next-pm', methods=['POST'])
def send_to_next_pm():
    try:
        data = request.get_json()
        print(f"Received data: {data}")
        project_id = data.get('project_id')

        if not project_id:
            return jsonify({'message': 'No project ID provided'}), 400

        # Fetch the project from the database
        project = mongo.db.project_details.find_one({'_id': ObjectId(project_id)})
        if not project:
            return jsonify({'message': 'Project not found'}), 404

        print(f"Project details: {project}")

        # Fetch all PMs
        pms = list(mongo.db.product_managers.find())
        print(f"PMs found: {pms}")

        # Use the pm_ranking to determine the next PM
        pm_ranking = project.get('pm_ranking', [])
        if pm_ranking:
            print(f"PM Ranking: {pm_ranking}")
            ranked_pm_ids = [ranked_pm['id'] for ranked_pm in pm_ranking]

            if len(ranked_pm_ids) > 1:
                next_pm_id = ranked_pm_ids[1]  # Get the next PM in the ranking list
                next_pm = mongo.db.product_managers.find_one({'_id': ObjectId(next_pm_id)})
                pm_ranking = [pm for pm in pm_ranking if pm['id'] != ranked_pm_ids[0]]  # Update ranking list
            else:
                print("Reached the final PM in the ranking list.")
                next_pm = None  # No more PMs to assign
        else:
            # Fallback: Use the get_next_pm function
            next_pm = get_next_pm(pms, project['tech_stack'], project['industry_vertical'], project['project_status'])

        current_pm_id = str(project.get('assigned_pm_id', ''))
        startup_id = str(project.get('startup_id'))

        if next_pm:
            print(f"Next PM: {next_pm}")

            # Ensure current_pm_id is not empty
            if not current_pm_id:
                raise ValueError('Assigned PM ID is not set in the project details')

            # Update project with the next PM and modified ranking
            mongo.db.project_details.update_one(
                {'_id': ObjectId(project_id)},
                {'$set': {
                    'assigned_pm': next_pm['name'],
                    'assigned_pm_id': str(next_pm['_id']),
                    'pm_ranking': pm_ranking
                }}
            )

            # Remove startup_id from the current PM's ideas array in pm_slots
            result = mongo.db.pm_slots.update_one(
                {'pm_id': current_pm_id},
                {'$pull': {'ideas': project_id}}
            )
            print(f"Update result: {result.raw_result}")

            return jsonify({'message': f'Project assigned to {next_pm["name"]}'}), 200
        
        else:
            print(f"No suitable PM found. Storing project {project_id} in Surplus.")
            # Store the project details in the Surplus collection
            mongo.db.surplus.insert_one({
                'project_id': project_id,
                'startup_id': project.get('startup_id'),
                'problem_statement': project.get('problem_statement'),
                'tech_stack': project.get('tech_stack'),
                'industry_vertical': project.get('industry_vertical'),
                'project_status': project.get('project_status'),
                'Feedback': project.get('Feedback'),
                'timestamp': datetime.datetime.utcnow()
            })

            # Remove assigned_pm, assigned_pm_id, pm_ranking from project_details
            mongo.db.project_details.update_one(
                {'_id': ObjectId(project_id)},
                {'$unset': {
                    'assigned_pm': '',
                    'assigned_pm_id': '',
                    'pm_ranking': ''
                }}
            )

            # Remove project_id from the ideas array in pm_slots for the last PM
            result = mongo.db.pm_slots.update_one(
                {'pm_id': current_pm_id},
                {'$pull': {'ideas': project_id}}
            )
            print(f"Update result after storing in Surplus: {result.raw_result}")

            return jsonify({'message': 'No suitable PM found, project stored in Surplus.'}), 200

    except Exception as e:
        print(f'Error: {e}')
        return jsonify({'message': 'An error occurred on the server'}), 500













@app.route('/surplus')
@login_required
def surplus():
    # Fetch all project details from the surplus collection
    surplus_projects = mongo.db.surplus.find()

    # Initialize the list to store projects with corresponding startup details
    projects_with_startup_details = []

    # Iterate through all surplus projects and fetch corresponding startup details
    for project in surplus_projects:
        # Get the startup_id from the project
        startup_id = project.get('startup_id')

        # Fetch the corresponding startup details using the startup_id
        startup_details = mongo.db.startup_details.find_one({"_id": ObjectId(startup_id)})

        # Append project and startup details to the list
        projects_with_startup_details.append({
            "project": project,
            "startup_details": startup_details
        })

    # Render the surplus page with all project details and corresponding startup details
    return render_template('surplus.html', user=current_user, projects=projects_with_startup_details)







@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    response = make_response(redirect(url_for('login')))
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/submit', methods=['POST'])
def submit():
    # Get data from the form
    form_data = {
        'name': request.form.get('name'),
        'email': request.form.get('email'),
        'bmc_video_link': request.form.get('bmc_video_link'),
        'startup_name': request.form.get('startup_name'),
        'problem_statement': request.form.get('problem_statement'),
        'description': request.form.get('description'),
        'current_status': request.form.get('current_status'),
        'sns_institution': request.form.get('sns_institution'),
        'team_details': request.form.get('team_details'),
        'industry_vertical': request.form.get('industry_vertical'),
        'industry_technology': request.form.get('industry_technology')
    }

    # Insert the data into MongoDB
    try:
        mongo.db.startup_details.insert_one(form_data)
        allot_projects()
    except Exception as e:
        return f"Error inserting data: {e}", 500

    # Render acknowledgment page
    return render_template('acknowledgment.html')

if __name__ == '__main__':
    app.run(debug=True)
