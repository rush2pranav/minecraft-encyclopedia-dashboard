"""
Minecraft Encyclopedia - Data Preparation & Analysis
=====================================================
Combines 15 relational tables from the Minecraft dataset, enriches with calculated metrics and produces Power BI ready CSVs. Also, helps to generate a crafting/drop network analysis.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images')
os.makedirs(IMG_DIR, exist_ok=True)

def load_all_tables():
    """Load all CSV files into a dictionary of dataframes"""
    tables = {}
    for f in os.listdir(DATA_DIR):
        if f.endswith('.csv'):
            name = f.replace('.csv', '')
            tables[name] = pd.read_csv(os.path.join(DATA_DIR, f), encoding='latin-1')
            print(f"  {name:25s} {len(tables[name]):>5} rows")
    return tables


def enrich_mobs(tables):
    """Create enriched mob dataset with drops and biome counts"""
    mobs = tables['Mobs'].copy()
    
    # count biomes each mob spawns in
    fauna_geo = tables['FaunaGeography']
    biome_counts = fauna_geo.groupby('mobID').size().reset_index(name='num_biomes')
    mobs = mobs.merge(biome_counts, left_on='ID', right_on='mobID', how='left')
    mobs['num_biomes'] = mobs['num_biomes'].fillna(0).astype(int)
    
    # count total drops ie food, ingredients, tools
    food_drops = tables['MobFoodDrops'].groupby('mobID').size().reset_index(name='food_drops')
    ingredient_drops = tables['MobIngredientDrops'].groupby('mobID').size().reset_index(name='ingredient_drops')
    tool_drops = tables['MobToolsAndArmorDrops'].groupby('mobID').size().reset_index(name='tool_drops')
    
    mobs = mobs.merge(food_drops, left_on='ID', right_on='mobID', how='left')
    mobs = mobs.drop(columns=['mobID'], errors='ignore')
    mobs = mobs.merge(ingredient_drops, left_on='ID', right_on='mobID', how='left')
    mobs = mobs.drop(columns=['mobID'], errors='ignore')
    mobs = mobs.merge(tool_drops, left_on='ID', right_on='mobID', how='left')
    mobs = mobs.drop(columns=['mobID'], errors='ignore')
    
    for col in ['food_drops', 'ingredient_drops', 'tool_drops']:
        mobs[col] = mobs[col].fillna(0).astype(int)
    mobs['total_drops'] = mobs['food_drops'] + mobs['ingredient_drops'] + mobs['tool_drops']
    
    # danger score ie health x damage which is normalized
    mobs['maxDamage'] = pd.to_numeric(mobs['maxDamage'], errors='coerce').fillna(0)
    mobs['healthPoints'] = pd.to_numeric(mobs['healthPoints'], errors='coerce').fillna(0)
    mobs['danger_score'] = (mobs['healthPoints'] * mobs['maxDamage']).round(0)
    
    # threat tier
    mobs['threat_tier'] = pd.cut(
        mobs['danger_score'],
        bins=[-1, 0, 100, 500, 2000, 99999],
        labels=['Passive', 'Low Threat', 'Medium Threat', 'High Threat', 'Boss']
    )
    
    # clean up duplicate mob column ids
    mobs = mobs.drop(columns=[c for c in mobs.columns if c == 'mobID'], errors='ignore')
    
    return mobs


def enrich_biomes(tables):
    """Create enriched biome dataset with entity and block counts"""
    biomes = tables['Biomes'].copy()
    dims = tables['Dimensions']
    
    # add dimension name
    biomes = biomes.merge(dims[['ID', 'name']], left_on='dimensionID', right_on='ID', 
                          how='left', suffixes=('', '_dimension'))
    biomes = biomes.rename(columns={'name_dimension': 'dimension_name'})
    biomes = biomes.drop(columns=['ID_dimension'], errors='ignore')
    
    # counts mobs per biome
    fauna_counts = tables['FaunaGeography'].groupby('biomeID').size().reset_index(name='num_mobs')
    biomes = biomes.merge(fauna_counts, left_on='ID', right_on='biomeID', how='left')
    biomes['num_mobs'] = biomes['num_mobs'].fillna(0).astype(int)
    
    # counts blocks per biome
    block_counts = tables['BlockGeography'].groupby('biomeID').size().reset_index(name='num_blocks')
    biomes = biomes.merge(block_counts, left_on='ID', right_on='biomeID', how='left')
    biomes['num_blocks'] = biomes['num_blocks'].fillna(0).astype(int)
    
    # counts flora per biome
    flora_counts = tables['FloraGeography'].groupby('biomeID').size().reset_index(name='num_flora')
    biomes = biomes.merge(flora_counts, left_on='ID', right_on='biomeID', how='left')
    biomes['num_flora'] = biomes['num_flora'].fillna(0).astype(int)
    
    # biodiversity score
    biomes['biodiversity_score'] = biomes['num_mobs'] + biomes['num_blocks'] + biomes['num_flora']
    
    # clean up
    biomes = biomes.drop(columns=[c for c in biomes.columns if c == 'biomeID'], errors='ignore')
    
    return biomes


def create_combined_items(tables):
    """Combine all item types into a single dataset for Power BI"""
    items = []
    
    # food
    food = tables['Food'].copy()
    food['item_category'] = 'Food'
    food['item_name'] = food['name']
    food = food.rename(columns={'hunger': 'primary_stat'})
    food['stat_label'] = 'Hunger Restored'
    items.append(food[['item_name', 'item_category', 'primary_stat', 'stat_label', 'type', 'debutDate', 'minecraftVersion']])
    
    # ingredients
    ingredients = tables['Ingredients'].copy()
    ingredients['item_category'] = 'Ingredient'
    ingredients['item_name'] = ingredients['name']
    ingredients['primary_stat'] = np.nan
    ingredients['stat_label'] = ''
    ingredients['type'] = 'Ingredient'
    items.append(ingredients[['item_name', 'item_category', 'primary_stat', 'stat_label', 'type', 'debutDate', 'minecraftVersion']])
    
    # tools and armor
    tools = tables['ToolsAndArmors'].copy()
    tools['item_category'] = 'Tools & Armor'
    tools['item_name'] = tools['name']
    tools['primary_stat'] = pd.to_numeric(tools['durability'], errors='coerce')
    tools['stat_label'] = 'Durability'
    items.append(tools[['item_name', 'item_category', 'primary_stat', 'stat_label', 'type', 'debutDate', 'minecraftVersion']])
    
    # landscape blocks
    blocks = tables['LandscapeBlocks'].copy()
    blocks['item_category'] = 'Landscape Block'
    blocks['item_name'] = blocks['name']
    blocks['primary_stat'] = np.nan
    blocks['stat_label'] = ''
    blocks['type'] = blocks['blockType']
    items.append(blocks[['item_name', 'item_category', 'primary_stat', 'stat_label', 'type', 'debutDate', 'minecraftVersion']])
    
    # man made blocks
    manmade = tables['ManMadeBlocks'].copy()
    manmade['item_category'] = 'Man-Made Block'
    manmade['item_name'] = manmade['name']
    manmade['primary_stat'] = np.nan
    manmade['stat_label'] = ''
    manmade['type'] = 'Man-Made'
    items.append(manmade[['item_name', 'item_category', 'primary_stat', 'stat_label', 'type', 'debutDate', 'minecraftVersion']])
    
    # flora
    flora = tables['Flora'].copy()
    flora['item_category'] = 'Flora'
    flora['item_name'] = flora['name']
    flora['primary_stat'] = pd.to_numeric(flora['maxGrowthTime'], errors='coerce')
    flora['stat_label'] = 'Max Growth Time'
    flora['type'] = flora['growthType']
    items.append(flora[['item_name', 'item_category', 'primary_stat', 'stat_label', 'type', 'debutDate', 'minecraftVersion']])
    
    combined = pd.concat(items, ignore_index=True)
    return combined


def build_drop_network(tables):
    """Build a network graph of mob -> drop relationships"""
    G = nx.DiGraph()
    
    mobs = tables['Mobs']
    food = tables['Food']
    ingredients = tables['Ingredients']
    tools = tables['ToolsAndArmors']
    
    # add mob nodes
    for _, mob in mobs.iterrows():
        G.add_node(mob['name'], node_type='mob', behavior=mob['behaviorTypes'],
                   health=mob.get('healthPoints', 0))
    
    # add food drop edges
    for _, row in tables['MobFoodDrops'].iterrows():
        mob_name = mobs[mobs['ID'] == row['mobID']]['name'].values
        food_name = food[food['ID'] == row['foodID']]['name'].values
        if len(mob_name) > 0 and len(food_name) > 0:
            G.add_node(food_name[0], node_type='food')
            G.add_edge(mob_name[0], food_name[0], drop_type='food')
    
    # add ingredient drop edges
    for _, row in tables['MobIngredientDrops'].iterrows():
        mob_name = mobs[mobs['ID'] == row['mobID']]['name'].values
        ing_name = ingredients[ingredients['ID'] == row['ingredientID']]['name'].values
        if len(mob_name) > 0 and len(ing_name) > 0:
            G.add_node(ing_name[0], node_type='ingredient')
            G.add_edge(mob_name[0], ing_name[0], drop_type='ingredient')
    
    # add tool/armor drop edges
    for _, row in tables['MobToolsAndArmorDrops'].iterrows():
        mob_name = mobs[mobs['ID'] == row['mobID']]['name'].values
        tool_name = tools[tools['ID'] == row['toolsAndArmorID']]['name'].values
        if len(mob_name) > 0 and len(tool_name) > 0:
            G.add_node(tool_name[0], node_type='tool')
            G.add_edge(mob_name[0], tool_name[0], drop_type='tool')
    
    return G


def visualize_network(G):
    """Create a visualization of the mob drop network"""
    fig, ax = plt.subplots(figsize=(20, 16))
    
    color_map = {'mob': '#FF4444', 'food': '#44FF44', 'ingredient': '#4488FF', 'tool': '#FFAA44'}
    node_colors = [color_map.get(G.nodes[n].get('node_type', 'mob'), '#888') for n in G.nodes]
    
    edge_colors = {'food': '#44FF44', 'ingredient': '#4488FF', 'tool': '#FFAA44'}
    e_colors = [edge_colors.get(G.edges[e].get('drop_type', ''), '#888') for e in G.edges]
    
    node_sizes = [300 if G.nodes[n].get('node_type') == 'mob' else 150 for n in G.nodes]
    
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=e_colors, alpha=0.4, arrows=True, 
                           arrowsize=10, width=0.8)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, 
                           alpha=0.8, edgecolors='white', linewidths=0.5)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=6, font_color='white')
    
    ax.set_facecolor('#0d1117')
    fig.patch.set_facecolor('#0d1117')
    
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#FF4444', label=f'Mobs ({sum(1 for n in G.nodes if G.nodes[n].get("node_type") == "mob")})'),
        Patch(facecolor='#44FF44', label=f'Food Drops ({sum(1 for n in G.nodes if G.nodes[n].get("node_type") == "food")})'),
        Patch(facecolor='#4488FF', label=f'Ingredients ({sum(1 for n in G.nodes if G.nodes[n].get("node_type") == "ingredient")})'),
        Patch(facecolor='#FFAA44', label=f'Tools & Armor ({sum(1 for n in G.nodes if G.nodes[n].get("node_type") == "tool")})'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=10, 
              facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
    
    ax.set_title('Minecraft Mob -> Drop Network', fontsize=18, color='white', pad=20)
    plt.tight_layout()
    plt.savefig(os.path.join(IMG_DIR, 'mob_drop_network.png'), dpi=150, bbox_inches='tight',
                facecolor='#0d1117')
    plt.show()
    
    # network stats
    print(f"\n=== Network Statistics ===")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")
    print(f"  Most connected mobs (by out degree):")
    out_degrees = sorted(G.out_degree(), key=lambda x: x[1], reverse=True)
    for node, degree in out_degrees[:10]:
        if G.nodes[node].get('node_type') == 'mob':
            print(f"    {node}: {degree} drops")


def visualize_mob_analysis(mobs):
    """Create mob analysis visualizations"""
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.patch.set_facecolor('#0d1117')
    for ax in axes.flatten():
        ax.set_facecolor('#161b22')
    
    # 1 - threat tier distribution
    colors_threat = {'Passive': '#4CAF50', 'Low Threat': '#8BC34A', 'Medium Threat': '#FF9800', 
                     'High Threat': '#F44336', 'Boss': '#9C27B0'}
    threat_counts = mobs['threat_tier'].value_counts()
    threat_counts.plot(kind='bar', ax=axes[0, 0], 
                       color=[colors_threat.get(str(t), '#888') for t in threat_counts.index])
    axes[0, 0].set_title('Mob Threat Tier Distribution', color='white', fontsize=14)
    axes[0, 0].set_xlabel('')
    axes[0, 0].set_ylabel('Count', color='white')
    axes[0, 0].tick_params(colors='white', rotation=30)
    
    # 2 - health vs damage scatter
    hostile = mobs[mobs['maxDamage'] > 0]
    axes[0, 1].scatter(hostile['healthPoints'], hostile['maxDamage'], 
                       s=hostile['total_drops'] * 30 + 50, alpha=0.7, c='#FF5722', edgecolors='white')
    for _, mob in hostile.iterrows():
        axes[0, 1].annotate(mob['name'], (mob['healthPoints'], mob['maxDamage']), 
                           fontsize=6, color='white', ha='left')
    axes[0, 1].set_xlabel('Health Points', color='white')
    axes[0, 1].set_ylabel('Max Damage', color='white')
    axes[0, 1].set_title('Mob Health vs Damage (size = total drops)', color='white', fontsize=14)
    axes[0, 1].tick_params(colors='white')
    
    # 3 - behavior type distribution
    behavior_counts = mobs['behaviorTypes'].value_counts()
    behavior_counts.plot(kind='barh', ax=axes[1, 0], color='#2196F3')
    axes[1, 0].set_title('Mob Behavior Types', color='white', fontsize=14)
    axes[1, 0].set_xlabel('Count', color='white')
    axes[1, 0].tick_params(colors='white')
    
    # 4 - top mobs by biome coverage
    top_biome_mobs = mobs.nlargest(15, 'num_biomes')
    axes[1, 1].barh(top_biome_mobs['name'], top_biome_mobs['num_biomes'], color='#4CAF50')
    axes[1, 1].set_title('Most Widespread Mobs (by biome count)', color='white', fontsize=14)
    axes[1, 1].set_xlabel('Number of Biomes', color='white')
    axes[1, 1].tick_params(colors='white')
    axes[1, 1].invert_yaxis()
    
    plt.tight_layout()
    plt.savefig(os.path.join(IMG_DIR, 'mob_analysis.png'), dpi=150, bbox_inches='tight',
                facecolor='#0d1117')
    plt.show()


def visualize_biome_analysis(biomes):
    """Create biome analysis visualizations"""
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    fig.patch.set_facecolor('#0d1117')
    for ax in axes:
        ax.set_facecolor('#161b22')
    
    # 1 - top biomes by biodiversity
    top_bio = biomes.nlargest(15, 'biodiversity_score')
    bars = axes[0].barh(top_bio['name'], top_bio['biodiversity_score'], color='#4CAF50')
    axes[0].set_title('Most Biodiverse Biomes', color='white', fontsize=14)
    axes[0].set_xlabel('Biodiversity Score (mobs + blocks + flora)', color='white')
    axes[0].tick_params(colors='white')
    axes[0].invert_yaxis()
    
    # 2 - biome composition
    top_bio_comp = biomes.nlargest(15, 'biodiversity_score')[['name', 'num_mobs', 'num_blocks', 'num_flora']]
    top_bio_comp = top_bio_comp.set_index('name')
    top_bio_comp.plot(kind='barh', stacked=True, ax=axes[1], 
                      color=['#FF5722', '#2196F3', '#4CAF50'])
    axes[1].set_title('Biome Composition Breakdown', color='white', fontsize=14)
    axes[1].set_xlabel('Count', color='white')
    axes[1].tick_params(colors='white')
    axes[1].legend(['Mobs', 'Blocks', 'Flora'], facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
    axes[1].invert_yaxis()
    
    plt.tight_layout()
    plt.savefig(os.path.join(IMG_DIR, 'biome_analysis.png'), dpi=150, bbox_inches='tight',
                facecolor='#0d1117')
    plt.show()


def main():
    print("=" * 60)
    print("MINECRAFT ENCYCLOPEDIA - DATA PREPARATION")
    print("=" * 60)
    
    print("\n--- Loading tables ---")
    tables = load_all_tables()
    
    print("\n--- Enriching mobs ---")
    mobs = enrich_mobs(tables)
    mobs.to_csv(os.path.join(DATA_DIR, 'mobs_enriched.csv'), index=False)
    print(f"  Saved mobs_enriched.csv ({len(mobs)} rows)")
    
    print("\n--- Enriching biomes ---")
    biomes = enrich_biomes(tables)
    biomes.to_csv(os.path.join(DATA_DIR, 'biomes_enriched.csv'), index=False)
    print(f"  Saved biomes_enriched.csv ({len(biomes)} rows)")
    
    print("\n--- Creating combined items ---")
    items = create_combined_items(tables)
    items.to_csv(os.path.join(DATA_DIR, 'all_items_combined.csv'), index=False)
    print(f"  Saved all_items_combined.csv ({len(items)} rows)")
    
    print("\n--- Building drop network ---")
    G = build_drop_network(tables)
    visualize_network(G)
    
    print("\n--- Generating mob analysis ---")
    visualize_mob_analysis(mobs)
    
    print("\n--- Generating biome analysis ---")
    visualize_biome_analysis(biomes)
    
    print("\n=== SUMMARY ===")
    print(f"  Mobs: {len(mobs)} ({len(mobs[mobs['maxDamage'] > 0])} hostile)")
    print(f"  Biomes: {len(biomes)} across {biomes['dimension_name'].nunique()} dimensions")
    print(f"  Total items: {len(items)}")
    print(f"  Item categories: {items['item_category'].value_counts().to_dict()}")
    print(f"  Network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"\n  Files saved to: {DATA_DIR}")
    print(f"  Charts saved to: {IMG_DIR}")
    print(f"\n  Open the enriched CSVs in Power BI!")


if __name__ == '__main__':
    main()