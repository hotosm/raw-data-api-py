import asyncio
from osm_data_client import get_osm_data

async def main():
    """Example of using the OSM data client."""
    # Define an area in Midtown Manhattan, New York
    # This covers approximately the area around Times Square
    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [-73.989, 40.754],  # Southwest corner
            [-73.981, 40.754],  # Southeast corner
            [-73.981, 40.759],  # Northeast corner
            [-73.989, 40.759],  # Northwest corner
            [-73.989, 40.754]   # Close the polygon
        ]]
    }
    
    # Parameters focused on buildings and points of interest
    params = {
        "fileName": "nyc_times_square",
        "outputType": "geojson",
        "filters": {
            "tags": {
                "all_geometry": {
                    "join_or": {  
                        "building": [],      # Get all buildings
                        "amenity": [],       # Get all amenities (restaurants, etc.)
                        "tourism": [],       # Get tourist attractions
                        "shop": []           # Get all shops
                    }
                }
            },
            "attributes": {
                "all_geometry": [
                    # Basic identification
                    "name", "ref", "description",
                    
                    # Address components
                    "addr:street", "addr:housenumber", "addr:city", "addr:postcode",
                    
                    # Building characteristics
                    "building:levels", "height", "building:material", "building:use",
                    
                    # For amenities and shops
                    "amenity", "shop", "cuisine", "opening_hours", "tourism"
                ]
            }
        },
        "geometryType": ["polygon", "point"]  # Include both shapes
    }
    
    print("Starting OSM data extraction for Times Square area in NYC...")
    try:
        # Use the client to fetch data
        data = await get_osm_data(geometry, **params)
        
        # Process the results
        if 'features' in data and data['features']:
            feature_count = len(data['features'])
            print(f"Success! Found {feature_count} features in the selected area.")
            
            # Analyze the data
            categories = {}
            buildings = 0
            pois = 0
            named_features = 0
            
            for feature in data['features']:
                props = feature.get('properties', {})
                
                if props.get('name'):
                    named_features += 1
                    
                if props.get('building'):
                    buildings += 1
                    
                if props.get('amenity') or props.get('shop') or props.get('tourism'):
                    pois += 1
                    
                for key in ['building', 'amenity', 'shop', 'tourism']:
                    if props.get(key):
                        category = f"{key}={props.get(key)}"
                        categories[category] = categories.get(category, 0) + 1
            
            # Output summary
            print(f"\nSummary:")
            print(f"  Buildings: {buildings}")
            print(f"  Points of Interest: {pois}")
            print(f"  Named features: {named_features}")
            
            print("\nTop 10 feature categories:")
            for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {category}: {count}")
                
            if named_features > 0:
                print("\nSome notable places in this area:")
                notable = []
                for feature in data['features']:
                    props = feature.get('properties', {})
                    if props.get('name'):
                        notable.append((props.get('name'), 
                                      props.get('amenity') or props.get('shop') or 
                                      props.get('tourism') or props.get('building')))
                
                for name, type_info in notable[:10]:
                    print(f"  {name} ({type_info})")
                    
                if len(notable) > 10:
                    print(f"  ... and {len(notable) - 10} more named features")
        else:
            print("Response doesn't contain features. Check API parameters.")
            
    except Exception as e:
        print(f"Error extracting data: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
