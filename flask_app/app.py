import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from dotenv import load_dotenv

from database import supabase
from rules_engine import calculate_fertilizer_recommendation
from weather_service import get_current_weather

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

@app.route("/", methods=["GET"])
def index():
    if "farmer" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    mobile = request.form.get("mobile")
    otp = request.form.get("otp")
    
    if otp != "123456":
        return jsonify({"success": False, "message": "Invalid OTP"})
        
    try:
        response = supabase.table("farmers").select("*").eq("mobile", mobile).execute()
        farmers = response.data
        if not farmers:
            return jsonify({"success": False, "message": "Farmer not registered. Please register first."})
            
        farmer = farmers[0]
        session["farmer"] = farmer
        return jsonify({"success": True, "message": "Login successful"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/signup", methods=["POST"])
def signup():
    mobile = request.form.get("mobile")
    name = request.form.get("name")
    district = request.form.get("district")
    mandal = request.form.get("mandal")
    otp = request.form.get("otp")
    
    if otp != "123456":
        return jsonify({"success": False, "message": "Invalid OTP"})
        
    try:
        # Check if already exists
        existing = supabase.table("farmers").select("id").eq("mobile", mobile).execute()
        if existing.data:
            return jsonify({"success": False, "message": "Mobile number already registered"})
            
        new_farmer = {
            "mobile": mobile,
            "name": name,
            "district": district,
            "mandal": mandal,
            "language_preference": "en"
        }
        res = supabase.table("farmers").insert(new_farmer).execute()
        
        if res.data:
            session["farmer"] = res.data[0]
            return jsonify({"success": True, "message": "Registration successful"})
        return jsonify({"success": False, "message": "Failed to register"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/dashboard")
def dashboard():
    if "farmer" not in session:
        return redirect(url_for("index"))
        
    farmer = session["farmer"]
    # Get history
    history = []
    try:
        history_res = supabase.table("recommendations").select("*").eq("farmer_id", farmer["id"]).order("created_at", desc=True).limit(10).execute()
        for rec in history_res.data:
            rec_data = json.loads(rec["recommendation_json"])
            rec_data['created_at'] = rec["created_at"]
            history.append(rec_data)
    except Exception as e:
        print("Error fetching history", e)
        
    return render_template("dashboard.html", farmer=farmer, history=history)

@app.route("/recommendation/new", methods=["GET", "POST"])
def new_recommendation():
    if "farmer" not in session:
        return redirect(url_for("index"))
        
    farmer = session["farmer"]
    
    if request.method == "POST":
        crop_name = request.form.get("crop_name")
        variety = request.form.get("variety")
        district = request.form.get("district") or farmer["district"]
        mandal = request.form.get("mandal") or farmer["mandal"]
        area_sown = float(request.form.get("area_sown"))
        sowing_date_str = request.form.get("sowing_date")
        sowing_date = datetime.strptime(sowing_date_str, "%Y-%m-%d")
        
        try:
            # Create field
            field_data = {
                "farmer_id": farmer["id"],
                "location": f"{mandal}, {district}",
                "crop_type": crop_name,
                "variety": variety,
                "sowing_date": sowing_date_str,
                "area_sown": area_sown
            }
            field_res = supabase.table("fields").insert(field_data).execute()
            field_id = field_res.data[0]["id"] if field_res.data else None
            
            # Generate recommendation (Passing None for DB as we'll mock soil info in rules_engine)
            rec_data = calculate_fertilizer_recommendation(
                crop_name=crop_name,
                sowing_date=sowing_date,
                district=district,
                mandal=mandal,
                area_sown=area_sown,
                db=None, # Adapted parameter
                variety=variety
            )
            
            if field_id:
                rec_record = {
                    "farmer_id": farmer["id"],
                    "field_id": field_id,
                    "recommendation_json": json.dumps(rec_data, ensure_ascii=False)
                }
                supabase.table("recommendations").insert(rec_record).execute()
                
            session["last_recommendation"] = rec_data
            return redirect(url_for("results"))
        except Exception as e:
            flash(f"Error calculating recommendation: {str(e)}", "error")
            
    return render_template("recommendation_form.html", farmer=farmer)

@app.route("/results")
def results():
    if "farmer" not in session:
        return redirect(url_for("index"))
        
    rec_data = session.get("last_recommendation")
    if not rec_data:
        return redirect(url_for("dashboard"))
        
    return render_template("results.html", recommendation=rec_data, farmer=session["farmer"])

@app.route("/disease-detection")
def disease_detection():
    if "farmer" not in session:
        return redirect(url_for("index"))
    return render_template("disease_vision.html", farmer=session["farmer"])

@app.route("/api/disease-detection", methods=["POST"])
def api_disease_detection():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image uploaded"}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
        
    import tempfile
    import werkzeug.utils
    from disease_service import analyze_plant_disease
    
    filename = werkzeug.utils.secure_filename(file.filename)
    # Save the file temporarily
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)
    file.save(filepath)
    
    # Process using Gemini
    result = analyze_plant_disease(filepath)
    
    # Cleanup temp file
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass
            
    return jsonify(result)

@app.route("/book", methods=["GET", "POST"])
def book_fertilizers():
    if "farmer" not in session:
        return redirect(url_for("index"))
        
    farmer = session["farmer"]
    
    if request.method == "POST":
        fertilizer = request.form.get("fertilizer")
        quantity = float(request.form.get("quantity", 0))
        total_price = float(request.form.get("total_price", 0))
        delivery_address = request.form.get("delivery_address")
        payment_status = request.form.get("payment_status", "Pending")
        
        try:
            booking_data = {
                "farmer_id": farmer["id"],
                "fertilizer_name": fertilizer,
                "quantity_kg": quantity,
                "total_price": total_price,
                "delivery_address": delivery_address,
                "status": payment_status
            }
            supabase.table("bookings").insert(booking_data).execute()
        except Exception as e:
            print(f"Error booking: {e}")
            
        return redirect(url_for("book_fertilizers"))

    bookings = []
    try:
        book_res = supabase.table("bookings").select("*").eq("farmer_id", farmer["id"]).order("created_at", desc=True).limit(20).execute()
        bookings = book_res.data
    except Exception as e:
        print(f"Error fetching bookings: {e}")
        
    return render_template("booking.html", farmer=farmer, bookings=bookings)

@app.route("/api/weather")
def api_weather():
    district = request.args.get("district")
    mandal = request.args.get("mandal")
    try:
        data = get_current_weather(district, mandal)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=8000)
