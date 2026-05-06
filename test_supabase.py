from helpers.supabase_client import supabase
res = supabase.table("recipe_ingredients").select("*, ingredients(*)").eq("recipe_id", 0).execute()
print(res.data)
