from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from pytz import timezone
import os
import csv
from werkzeug.utils import secure_filename
import zipfile
import shutil

app = Flask(__name__, static_folder='templates')
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'templates'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure required directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# IST Timezone
IST = timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST)

# Serve static files and uploads
@app.route('/')
def serve_frontend():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

db = SQLAlchemy(app)

# Models
class Measurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)  # 'tds' or 'ph'
    rack = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: get_ist_now())

class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: get_ist_now())
    growth_records = db.relationship('GrowthRecord', backref='plant', lazy=True)
    notes = db.relationship('PlantNote', backref='plant', lazy=True)

class PlantNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: get_ist_now())

class GrowthRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'flowering' or 'fruiting'
    stage = db.Column(db.String(50), nullable=False)
    count = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    images = db.Column(db.Text)  # Comma-separated image filenames
    timestamp = db.Column(db.DateTime, default=lambda: get_ist_now())

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = get_ist_now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

@app.route('/api/measurements', methods=['POST'])
def add_measurements():
    data = request.json
    try:
        for rack, value in data['readings'].items():
            measurement = Measurement(
                type=data['type'],
                rack=int(rack),
                value=float(value)
            )
            db.session.add(measurement)
        db.session.commit()
        return jsonify({'message': 'Measurements saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/measurements/latest', methods=['GET'])
def get_latest_measurements():
    try:
        # Get latest measurements for each rack and type
        latest_tds = {}
        latest_ph = {}
        
        for rack in range(1, 5):
            tds_reading = Measurement.query.filter_by(
                type='tds', 
                rack=rack
            ).order_by(Measurement.timestamp.desc()).first()
            
            ph_reading = Measurement.query.filter_by(
                type='ph', 
                rack=rack
            ).order_by(Measurement.timestamp.desc()).first()
            
            if tds_reading:
                latest_tds[str(rack)] = tds_reading.value
            if ph_reading:
                latest_ph[str(rack)] = ph_reading.value
        
        # Calculate averages
        tds_avg = sum(latest_tds.values()) / len(latest_tds) if latest_tds else 0
        ph_avg = sum(latest_ph.values()) / len(latest_ph) if latest_ph else 0
        
        return jsonify({
            'tds': {
                'readings': latest_tds,
                'average': tds_avg
            },
            'ph': {
                'readings': latest_ph,
                'average': ph_avg
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/measurements/download', methods=['GET'])
def download_measurements():
    try:
        measurements = Measurement.query.order_by(Measurement.timestamp.desc()).all()
        
        # Create CSV file
        csv_filename = 'measurements.csv'
        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Timestamp', 'Type', 'Rack', 'Value'])
            
            for m in measurements:
                writer.writerow([
                    m.timestamp.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S'),
                    m.type,
                    m.rack,
                    m.value
                ])
        
        return send_file(
            csv_filename,
            mimetype='text/csv',
            as_attachment=True,
            download_name='farm_measurements.csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/plants', methods=['POST'])
def add_plant_note():
    try:
        plant_id = request.form.get('plant_id')
        note_text = request.form.get('notes')
        image = request.files.get('image')
        
        # Save image if provided
        image_filename = save_uploaded_file(image) if image else None
        
        # Find existing plant or create new one
        plant = Plant.query.filter_by(plant_id=plant_id).first()
        if not plant:
            plant = Plant(plant_id=plant_id)
            db.session.add(plant)
            db.session.flush()  # Get the plant id for the new plant
        
        # Create new note
        plant_note = PlantNote(
            plant_id=plant.id,
            note=note_text,
            image=image_filename
        )
        
        db.session.add(plant_note)
        db.session.commit()
        
        return jsonify({'message': 'Plant note saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# Update the growth record endpoint to handle plant creation
@app.route('/api/growth-records', methods=['POST'])
def add_growth_record():
    try:
        plant_id = request.form.get('plant_id')
        # First check if plant exists, if not create it
        plant = Plant.query.filter_by(plant_id=plant_id).first()
        if not plant:
            plant = Plant(plant_id=plant_id)
            db.session.add(plant)
            db.session.flush()  # Get the ID for the new plant
        
        # Save uploaded images
        images = request.files.getlist('images')
        image_filenames = []
        for image in images:
            filename = save_uploaded_file(image)
            if filename:
                image_filenames.append(filename)
        
        record = GrowthRecord(
            plant_id=plant.id,
            type=request.form.get('type'),
            stage=request.form.get('stage'),
            count=int(request.form.get('count')),
            notes=request.form.get('notes'),
            images=','.join(image_filenames) if image_filenames else None
        )
        
        db.session.add(record)
        db.session.commit()
        
        return jsonify({'message': 'Growth record saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/plants/<plant_id>/timeline', methods=['GET'])
def get_plant_timeline(plant_id):
    try:
        plant = Plant.query.filter_by(plant_id=plant_id).first()
        if not plant:
            return jsonify({'error': 'Plant not found'}), 404
        
        # Gather all events for the timeline
        timeline = []
        
        # Add plant creation event
        timeline.append({
            'type': 'plant_created',
            'date': plant.created_at.astimezone(IST).isoformat(),
            'notes': None,
            'image': None
        })
        
        # Add notes
        for note in plant.notes:
            timeline.append({
                'type': 'note',
                'date': note.created_at.astimezone(IST).isoformat(),
                'notes': note.note,
                'image': note.image
            })
        
        # Add growth records
        for record in plant.growth_records:
            timeline.append({
                'type': f'{record.type}_record',
                'date': record.timestamp.astimezone(IST).isoformat(),
                'stage': record.stage,
                'count': record.count,
                'notes': record.notes,
                'images': record.images.split(',') if record.images else []
            })
        
        # Sort timeline by date
        timeline.sort(key=lambda x: x['date'])  # Changed to chronological order
        
        return jsonify({
            'plant_id': plant.plant_id,
            'timeline': timeline
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
@app.route('/api/plants/download-all', methods=['GET'])
def download_all_plants_data():
    try:
        # Prepare a temporary folder for all plants
        all_plants_folder = os.path.join(UPLOAD_FOLDER, "all_plants_data")
        os.makedirs(all_plants_folder, exist_ok=True)
        
        # Fetch all plants
        plants = Plant.query.all()
        
        if not plants:
            return jsonify({'error': 'No plants found'}), 404
        
        # Process each plant
        for plant in plants:
            plant_folder = os.path.join(all_plants_folder, plant.plant_id)
            images_folder = os.path.join(plant_folder, 'images')
            os.makedirs(images_folder, exist_ok=True)
            
            # Copy images
            for note in plant.notes:
                if note.image:
                    image_path = os.path.join(UPLOAD_FOLDER, note.image)
                    if os.path.exists(image_path):
                        shutil.copy(image_path, images_folder)
            
            for record in plant.growth_records:
                if record.images:
                    for image_name in record.images.split(','):
                        image_path = os.path.join(UPLOAD_FOLDER, image_name)
                        if os.path.exists(image_path):
                            shutil.copy(image_path, images_folder)
            
            # Create CSV for the plant
            csv_path = os.path.join(plant_folder, f"{plant.plant_id}_data.csv")
            with open(csv_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Type', 'Date', 'Details', 'Notes', 'Images'])
                
                # Add plant creation details
                writer.writerow([
                    'Plant Created',
                    plant.created_at.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S'),
                    None,
                    None,
                    None
                ])
                
                # Add notes
                for note in plant.notes:
                    writer.writerow([
                        'Note',
                        note.created_at.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S'),
                        note.note,
                        None,
                        note.image or None
                    ])
                
                # Add growth records
                for record in plant.growth_records:
                    writer.writerow([
                        f"{record.type.capitalize()} Record",
                        record.timestamp.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S'),
                        f"Stage: {record.stage}, Count: {record.count}",
                        record.notes or None,
                        record.images
                    ])
        
        # Zip the folder
        zip_filename = os.path.join(UPLOAD_FOLDER, "all_plants_data.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for root, dirs, files in os.walk(all_plants_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, all_plants_folder)
                    zipf.write(file_path, arcname)
        
        # Clean up the temporary folder
        shutil.rmtree(all_plants_folder)
        
        # Return the zip file
        return send_file(
            zip_filename,
            as_attachment=True,
            mimetype='application/zip',
            download_name="all_plants_data.zip"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
@app.route('/api/plants/all', methods=['GET'])
def get_all_plants():
    try:
        plants = Plant.query.all()
        plants_data = []
        
        for plant in plants:
            # Get the latest image
            latest_image = None
            latest_stage = None
            
            # Check growth records for latest image and stage
            if plant.growth_records:
                latest_record = max(plant.growth_records, key=lambda x: x.timestamp)
                if latest_record.images:
                    latest_image = latest_record.images.split(',')[0]
                latest_stage = latest_record.stage
            # Check notes for image if no growth record image
            elif plant.notes:
                latest_note = max(plant.notes, key=lambda x: x.created_at)
                if latest_note.image:
                    latest_image = latest_note.image

            plants_data.append({
                'plant_id': plant.plant_id,
                'latest_image': latest_image,
                'latest_stage': latest_stage,
                'total_records': len(plant.growth_records) + len(plant.notes),
                'created_at': plant.created_at.isoformat()
            })
        
        return jsonify({'plants': plants_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True,host='0.0.0.0')
