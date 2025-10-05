
from flask import Flask, jsonify
from discovery import get_devices
from analyzer import get_activity



app = Flask(__name__) # app name 

@app.route('/') # "home page" button if this is clicked it starts the serer and runs the code under 
def home():
    return jsonify({'message': 'Hello, World!'})



@app.route('/discovery')  # defines a new route (URL)
def discovery():
    return jsonify(get_devices())  # runs the function and sends back JSON data

# route for activity
@app.route('/activity')
def activity():
    return jsonify(get_activity())





if __name__ == '__main__': # make sure the flasks is only run on this file 
    app.run(debug=True)  # helps automatically reload the server when code changes
