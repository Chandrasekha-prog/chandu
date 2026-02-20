import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from weather_service import get_current_weather, get_weather_forecast, analyze_weather_for_fertilizer
from stage_calculator import calculate_stage_schedule

# Load crop data
CROP_DATA_PATH = os.path.join(os.path.dirname(__file__), "crop_data.json")
with open(CROP_DATA_PATH, 'r', encoding='utf-8') as f:
    CROP_DATA = json.load(f)

def calculate_crop_stage(sowing_date: datetime, current_date: datetime = None) -> str:
    """Calculate current crop growth stage based on days after sowing"""
    if current_date is None:
        current_date = datetime.now()
    
    days_after_sowing = (current_date - sowing_date).days
    
    if days_after_sowing < 0:
        return "not_sown"
    elif days_after_sowing <= 30:
        return "vegetative"
    elif days_after_sowing <= 60:
        return "flowering"
    else:
        return "ripening"

def get_crop_stage_for_crop(crop_name: str, sowing_date: datetime, current_date: datetime = None) -> Dict:
    """Get specific crop stage based on crop type"""
    if current_date is None:
        current_date = datetime.now()
    
    days_after_sowing = (current_date - sowing_date).days
    
    # Get crop data
    crop_info = CROP_DATA['crops'].get(crop_name, None)
    if not crop_info:
        # Default stages
        return {
            "stage": calculate_crop_stage(sowing_date, current_date),
            "days_after_sowing": days_after_sowing,
            "description": "Growth stage"
        }
    
    # Determine stage based on crop-specific days
    stages = crop_info['growth_stages']
    for stage_name, stage_info in stages.items():
        if stage_info['days'][0] <= days_after_sowing <= stage_info['days'][1]:
            return {
                "stage": stage_name,
                "days_after_sowing": days_after_sowing,
                "description": stage_info['description']
            }
    
    # If beyond all stages, return ripening
    return {
        "stage": "ripening",
        "days_after_sowing": days_after_sowing,
        "description": "Maturity stage"
    }

def get_soil_parameters(db, district: str = None, mandal: str = None) -> Optional[Dict]:
    """Get soil parameters from database based on location"""
    # For now, return mock average/typical values since we don't have direct mapping
    return {
        "N": 250,  # kg/ha (low)
        "P": 15,   # kg/ha (medium)
        "K": 150,  # kg/ha (low)
        "pH": 6.5,
        "OC": 0.5  # Organic carbon %
    }

def calculate_fertilizer_recommendation(
    crop_name: str,
    sowing_date: datetime,
    district: str,
    mandal: str,
    area_sown: float,
    db, # Kept for signature compatibility but unused
    variety: str = None,
    include_weather: bool = True
) -> Dict:
    """
    Main function to calculate fertilizer recommendation
    """
    
    # Get crop stage
    crop_stage_info = get_crop_stage_for_crop(crop_name, sowing_date)
    stage = crop_stage_info['stage']
    
    # Get soil parameters
    soil_params = get_soil_parameters(db, district, mandal)
    
    # Get crop data
    crop_info = CROP_DATA['crops'].get(crop_name, None)
    if not crop_info:
        # Use default values for unknown crops
        crop_info = CROP_DATA['crops']['వరి']  # Default to rice
    
    # Get nutrient requirements for current stage
    nutrient_req = crop_info['nutrient_requirements'].get(stage, {"N": 40, "P": 20, "K": 20})
    
    # Calculate fertilizer needs based on soil deficiency
    thresholds = CROP_DATA['soil_thresholds']
    fertilizers = []
    total_cost = 0
    
    # Nitrogen (Urea)
    if soil_params['N'] < thresholds['N']['medium']:
        n_needed = nutrient_req['N'] * area_sown  # kg
        urea_amount = (n_needed * 100) / CROP_DATA['fertilizer_types']['Urea']['percentage']
        urea_cost = urea_amount * CROP_DATA['fertilizer_types']['Urea']['price_per_kg']
        
        fertilizers.append({
            "type": "Urea",
            "name": "Urea",
            "telugu_name": CROP_DATA['fertilizer_types']['Urea']['telugu_name'],
            "amount_kg": round(urea_amount, 2),
            "amount_per_acre": round(urea_amount / area_sown, 2),
            "timing": "Immediate" if stage == "vegetative" else f"During {stage} stage",
            "cost": round(urea_cost, 2),
            "nutrient": "N"
        })
        total_cost += urea_cost
    
    # Phosphorus (DAP)
    if soil_params['P'] < thresholds['P']['medium']:
        p_needed = nutrient_req['P'] * area_sown  # kg
        dap_amount = (p_needed * 100) / CROP_DATA['fertilizer_types']['DAP']['percentage']
        dap_cost = dap_amount * CROP_DATA['fertilizer_types']['DAP']['price_per_kg']
        
        fertilizers.append({
            "type": "DAP",
            "name": "DAP",
            "telugu_name": CROP_DATA['fertilizer_types']['DAP']['telugu_name'],
            "amount_kg": round(dap_amount, 2),
            "amount_per_acre": round(dap_amount / area_sown, 2),
            "timing": "Basal application" if stage == "vegetative" else f"During {stage} stage",
            "cost": round(dap_cost, 2),
            "nutrient": "P"
        })
        total_cost += dap_cost
    
    # Potassium (MOP)
    if soil_params['K'] < thresholds['K']['medium']:
        k_needed = nutrient_req['K'] * area_sown  # kg
        mop_amount = (k_needed * 100) / CROP_DATA['fertilizer_types']['MOP']['percentage']
        mop_cost = mop_amount * CROP_DATA['fertilizer_types']['MOP']['price_per_kg']
        
        fertilizers.append({
            "type": "MOP",
            "name": "MOP",
            "telugu_name": CROP_DATA['fertilizer_types']['MOP']['telugu_name'],
            "amount_kg": round(mop_amount, 2),
            "amount_per_acre": round(mop_amount / area_sown, 2),
            "timing": f"During {stage} stage",
            "cost": round(mop_cost, 2),
            "nutrient": "K"
        })
        total_cost += mop_cost
    
    # Base notes
    notes = [
        "Apply fertilizers in split doses for better efficiency",
        "Ensure adequate soil moisture before application"
    ]
    
    # Get weather data and analysis
    weather_data = None
    weather_analysis = None
    forecast = None
    
    if include_weather:
        try:
            weather_data = get_current_weather(district, mandal)
            forecast = get_weather_forecast(district, mandal)
            weather_analysis = analyze_weather_for_fertilizer(weather_data, forecast)
            
            # Add weather-based notes
            if weather_analysis['weather_notes']:
                notes = weather_analysis['weather_notes'] + notes
            
        except Exception as e:
            print(f"Error getting weather data: {e}")
            # Continue without weather data
            notes.insert(0, "Weather data unavailable - check conditions before application")
    
    # Generate recommendation
    recommendation = {
        "crop": crop_name,
        "english_name": crop_info.get('english_name', crop_name),
        "variety": variety,
        "area_sown": area_sown,
        "sowing_date": sowing_date.strftime("%Y-%m-%d"),
        "current_stage": stage,
        "days_after_sowing": crop_stage_info['days_after_sowing'],
        "stage_description": crop_stage_info['description'],
        "fertilizers": fertilizers,
        "total_cost": round(total_cost, 2),
        "expected_yield_increase": "10-15%",
        "soil_parameters": soil_params,
        "notes": notes,
        "district": district,
        "mandal": mandal,
        "weather": weather_data,
        "weather_analysis": weather_analysis,
        "forecast": forecast,
        "organic_recommendations": {
            "manures": CROP_DATA.get('organic_options', {}).get('manures', []),
            "bio_fertilizers": [
                 bf for bf in CROP_DATA.get('organic_options', {}).get('bio_fertilizers', [])
                 if "All Crops" in bf.get('crops', []) or 
                    any(c.lower() in [x.lower() for x in bf.get('crops', [])] for c in [crop_name, crop_info.get('english_name', '')])
            ],
            "green_manures": CROP_DATA.get('organic_options', {}).get('green_manures', [])
        }
    }
    
    # Calculate stage-based fertilizer schedule
    try:
        # Map crop name to English to avoid Unicode issues in server environment
        english_crop_map = {
             "వరి": "Paddy",
             "పత్తి": "Cotton",
             "మొక్కజొన్న": "Maize",
             "వేరుశనగ": "Groundnut",
             "మినుము": "Blackgram",
             "పెసర": "Green Gram"
        }
        calc_crop_name = english_crop_map.get(crop_name, crop_name)

        stage_schedule = calculate_stage_schedule(
            crop=calc_crop_name,
            sowing_date=sowing_date.strftime("%Y-%m-%d"),
            total_fertilizers=fertilizers,
            area_sown=area_sown
        )
        recommendation["stage_schedule"] = stage_schedule
    except Exception as e:
        print(f"Error calculating stage schedule: {repr(e)}")
        recommendation["stage_schedule"] = None
    
    return recommendation

def get_available_crops(db) -> List[Dict]:
    """Get list of available crops from database"""
    # Simply load from crop_data.json
    crop_list = []
    
    for crop_name, crop_info in CROP_DATA['crops'].items():
        crop_list.append({
            "telugu_name": crop_name,
            "english_name": crop_info['english_name']
        })
    
    return crop_list
