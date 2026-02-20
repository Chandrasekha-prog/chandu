"""
Stage-based fertilizer calculator for crop recommendations.
Calculates fertilizer application schedule across different growth stages.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Crop growth stage definitions (days after sowing)
CROP_STAGES = {
    "paddy": [
        {"name": "Basal", "name_te": "బేసల్", "days": 0, "duration": 7, "icon": "🌱"},
        {"name": "Tillering", "name_te": "టిల్లరింగ్", "days": 15, "duration": 15, "icon": "🌿"},
        {"name": "Panicle Initiation", "name_te": "పానికల్ ఇనిషియేషన్", "days": 45, "duration": 10, "icon": "🌾"},
        {"name": "Flowering", "name_te": "పుష్పించడం", "days": 65, "duration": 10, "icon": "🌸"},
        {"name": "Grain Filling", "name_te": "ధాన్యం నింపడం", "days": 85, "duration": 10, "icon": "🌾"},
    ],
    "cotton": [
        {"name": "Basal", "name_te": "బేసల్", "days": 0, "duration": 7, "icon": "🌱"},
        {"name": "Vegetative", "name_te": "వృద్ధి దశ", "days": 30, "duration": 20, "icon": "🌿"},
        {"name": "Square Formation", "name_te": "స్క్వేర్ ఏర్పాటు", "days": 60, "duration": 15, "icon": "🔲"},
        {"name": "Flowering", "name_te": "పుష్పించడం", "days": 80, "duration": 20, "icon": "🌸"},
        {"name": "Boll Development", "name_te": "బోల్ అభివృద్ధి", "days": 110, "duration": 20, "icon": "⚪"},
    ],
    "maize": [
        {"name": "Basal", "name_te": "బేసల్", "days": 0, "duration": 7, "icon": "🌱"},
        {"name": "Vegetative", "name_te": "వృద్ధి దశ", "days": 20, "duration": 15, "icon": "🌿"},
        {"name": "Tasseling", "name_te": "టాసెలింగ్", "days": 45, "duration": 10, "icon": "🌾"},
        {"name": "Silking", "name_te": "సిల్కింగ్", "days": 60, "duration": 10, "icon": "🌸"},
        {"name": "Grain Filling", "name_te": "ధాన్యం నింపడం", "days": 75, "duration": 15, "icon": "🌽"},
    ],
}

# NPK split ratios for different crops
# Format: {nutrient: {stage_name: ratio}}
NPK_SPLITS = {
    "paddy": {
        "N": {"Basal": 0.25, "Tillering": 0.50, "Panicle Initiation": 0.25},
        "P": {"Basal": 1.0},
        "K": {"Basal": 0.50, "Panicle Initiation": 0.50}
    },
    "cotton": {
        "N": {"Basal": 0.25, "Vegetative": 0.25, "Square Formation": 0.25, "Flowering": 0.25},
        "P": {"Basal": 1.0},
        "K": {"Basal": 0.33, "Square Formation": 0.33, "Flowering": 0.34}
    },
    "maize": {
        "N": {"Basal": 0.30, "Vegetative": 0.40, "Tasseling": 0.30},
        "P": {"Basal": 1.0},
        "K": {"Basal": 0.50, "Tasseling": 0.50}
    },
}

# Application instructions for each stage
STAGE_INSTRUCTIONS = {
    "Basal": {
        "en": "Apply during final land preparation. Mix thoroughly with soil before sowing or transplanting.",
        "te": "చివరి భూమి తయారీ సమయంలో వర్తించండి. విత్తడం లేదా నాటడం ముందు మట్టితో బాగా కలపండి."
    },
    "Tillering": {
        "en": "Apply as top dressing when tillers start forming. Apply after irrigation or rain.",
        "te": "టిల్లర్లు ఏర్పడటం ప్రారంభించినప్పుడు టాప్ డ్రెస్సింగ్‌గా వర్తించండి. నీటిపారుదల లేదా వర్షం తర్వాత వర్తించండి."
    },
    "Panicle Initiation": {
        "en": "Apply before panicle emergence. Ensure adequate soil moisture for better uptake.",
        "te": "పానికల్ ఆవిర్భావానికి ముందు వర్తించండి. మెరుగైన శోషణ కోసం తగినంత నేల తేమను నిర్ధారించండి."
    },
    "Vegetative": {
        "en": "Apply during active vegetative growth. Split into 2 applications if needed.",
        "te": "క్రియాశీల వృద్ధి సమయంలో వర్తించండి. అవసరమైతే 2 అప్లికేషన్లుగా విభజించండి."
    },
    "Square Formation": {
        "en": "Apply when squares start forming. Critical stage for boll development.",
        "te": "స్క్వేర్లు ఏర్పడటం ప్రారంభించినప్పుడు వర్తించండి. బోల్ అభివృద్ధికి కీలకమైన దశ."
    },
    "Flowering": {
        "en": "Apply at flowering stage. Helps in better flower and fruit development.",
        "te": "పుష్పించే దశలో వర్తించండి. మెరుగైన పువ్వు మరియు పండు అభివృద్ధికి సహాయపడుతుంది."
    },
    "Grain Filling": {
        "en": "Apply during grain filling stage. Ensures proper grain development.",
        "te": "ధాన్యం నింపే దశలో వర్తించండి. సరైన ధాన్యం అభివృద్ధిని నిర్ధారిస్తుంది."
    },
    "Tasseling": {
        "en": "Apply at tasseling stage. Critical for cob development.",
        "te": "టాసెలింగ్ దశలో వర్తించండి. కాబ్ అభివృద్ధికి కీలకం."
    },
    "Silking": {
        "en": "Apply during silking. Important for kernel formation.",
        "te": "సిల్కింగ్ సమయంలో వర్తించండి. కెర్నల్ ఏర్పాటుకు ముఖ్యం."
    },
    "Boll Development": {
        "en": "Apply during boll development. Ensures good boll size and quality.",
        "te": "బోల్ అభివృద్ధి సమయంలో వర్తించండి. మంచి బోల్ పరిమాణం మరియు నాణ్యతను నిర్ధారిస్తుంది."
    },
}


def get_nutrient_from_fertilizer(fertilizer_name: str) -> Dict[str, float]:
    """Extract NPK content from fertilizer name"""
    nutrient_content = {
        "urea": {"N": 0.46, "P": 0, "K": 0},
        "dap": {"N": 0.18, "P": 0.46, "K": 0},
        "ssp": {"N": 0, "P": 0.16, "K": 0},
        "mop": {"N": 0, "P": 0, "K": 0.60},
        "potash": {"N": 0, "P": 0, "K": 0.60},
        "complex": {"N": 0.10, "P": 0.26, "K": 0.26},
        "19:19:19": {"N": 0.19, "P": 0.19, "K": 0.19},
        "20:20:0": {"N": 0.20, "P": 0.20, "K": 0},
    }
    
    name_lower = fertilizer_name.lower()
    for key, content in nutrient_content.items():
        if key in name_lower:
            return content
    
    return {"N": 0, "P": 0, "K": 0}


def calculate_stage_schedule(
    crop: str,
    sowing_date: str,
    total_fertilizers: List[Dict[str, Any]],
    area_sown: float
) -> Dict[str, Any]:
    """
    Calculate stage-based fertilizer application schedule.
    
    Args:
        crop: Crop name (e.g., "paddy", "cotton")
        sowing_date: Sowing date in YYYY-MM-DD format
        total_fertilizers: List of total fertilizer recommendations
        area_sown: Area in acres
        
    Returns:
        Dictionary containing stage-based schedule
    """
    # Normalize crop name
    crop_lower = crop.lower()
    if "paddy" in crop_lower or "rice" in crop_lower or "వరి" in crop_lower:
        crop_key = "paddy"
    elif "cotton" in crop_lower or "పత్తి" in crop_lower:
        crop_key = "cotton"
    elif "maize" in crop_lower or "corn" in crop_lower or "మొక్కజొన్న" in crop_lower:
        crop_key = "maize"
    else:
        crop_key = "paddy"  # Default to paddy
    
    # Get stages for this crop
    stages_info = CROP_STAGES.get(crop_key, CROP_STAGES["paddy"])
    npk_splits = NPK_SPLITS.get(crop_key, NPK_SPLITS["paddy"])
    
    # Parse sowing date
    sow_date = datetime.strptime(sowing_date, "%Y-%m-%d")
    
    # Calculate total NPK from fertilizers
    total_npk = {"N": 0, "P": 0, "K": 0}
    for fert in total_fertilizers:
        fert_name = fert.get("name", fert.get("type", ""))
        nutrient_content = get_nutrient_from_fertilizer(fert_name)
        amount = fert["amount_kg"]
        for nutrient in ["N", "P", "K"]:
            total_npk[nutrient] += amount * nutrient_content[nutrient]
    
    # Build stage schedule
    stages = []
    for stage_info in stages_info:
        stage_name = stage_info["name"]
        days_after_sowing = stage_info["days"]
        application_date = sow_date + timedelta(days=days_after_sowing)
        
        # Calculate fertilizers for this stage
        stage_fertilizers = []
        
        # Check each nutrient
        for nutrient in ["N", "P", "K"]:
            if stage_name in npk_splits[nutrient]:
                ratio = npk_splits[nutrient][stage_name]
                nutrient_amount = total_npk[nutrient] * ratio
                
                # Find appropriate fertilizer
                if nutrient == "N" and nutrient_amount > 0:
                    urea_amount = nutrient_amount / 0.46  # Urea is 46% N
                    stage_fertilizers.append({
                        "name": "Urea",
                        "name_te": "యూరియా",
                        "amount_kg": round(urea_amount, 2),
                        "amount_per_acre": round(urea_amount / area_sown, 2),
                        "nutrient": "N",
                        "percentage": f"{ratio * 100:.0f}% of total N"
                    })
                elif nutrient == "P" and nutrient_amount > 0:
                    dap_amount = nutrient_amount / 0.46  # DAP is 46% P
                    stage_fertilizers.append({
                        "name": "DAP",
                        "name_te": "డిఎపి",
                        "amount_kg": round(dap_amount, 2),
                        "amount_per_acre": round(dap_amount / area_sown, 2),
                        "nutrient": "P",
                        "percentage": f"{ratio * 100:.0f}% of total P"
                    })
                elif nutrient == "K" and nutrient_amount > 0:
                    mop_amount = nutrient_amount / 0.60  # MOP is 60% K
                    stage_fertilizers.append({
                        "name": "MOP",
                        "name_te": "ఎంఓపి",
                        "amount_kg": round(mop_amount, 2),
                        "amount_per_acre": round(mop_amount / area_sown, 2),
                        "nutrient": "K",
                        "percentage": f"{ratio * 100:.0f}% of total K"
                    })
        
        # Get instructions
        instructions = STAGE_INSTRUCTIONS.get(stage_name, {
            "en": "Apply as recommended by agricultural expert.",
            "te": "వ్యవసాయ నిపుణుల సిఫార్సు ప్రకారం వర్తించండి."
        })
        
        stages.append({
            "stage_name": stage_name,
            "stage_name_te": stage_info["name_te"],
            "icon": stage_info["icon"],
            "days_after_sowing": days_after_sowing,
            "duration_days": stage_info["duration"],
            "application_date": application_date.strftime("%Y-%m-%d"),
            "application_date_formatted": application_date.strftime("%b %d, %Y"),
            "fertilizers": stage_fertilizers,
            "instructions_en": instructions["en"],
            "instructions_te": instructions["te"],
        })
    
    return {
        "crop": crop,
        "crop_key": crop_key,
        "sowing_date": sowing_date,
        "sowing_date_formatted": sow_date.strftime("%b %d, %Y"),
        "total_duration_days": stages_info[-1]["days"] + stages_info[-1]["duration"],
        "area_sown": area_sown,
        "stages": stages,
        "total_stages": len(stages)
    }
