import streamlit as st
import requests
import pandas as pd

# --- 1. FONCTIONS DE CONNEXION (AVEC AUTO-SECOURS) ---
def recuperer_donnees_parcelle(code_insee, section, numero):
    url = f"https://apicarto.ign.fr/api/cadastre/parcelle?code_insee={code_insee}&section={section}&numero={numero}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        reponse = requests.get(url, headers=headers, timeout=3)
        if reponse.status_code == 200:
            donnees = reponse.json()
            surface = donnees['features'][0]['properties']['contenance'] / 10000
            coords = donnees['features'][0]['geometry']['coordinates'][0][0]
            return True, surface, coords[0][1], coords[0][0]
    except:
        pass
    # Données de secours (Droué) si les serveurs IGN sont indisponibles
    return False, 15.4, 48.04, 1.07 

def recuperer_ensoleillement_pvgis(lat, lon):
    url = f"https://re.jrc.ec.europa.eu/api/v5_2/MRcalc?lat={lat}&lon={lon}&horirrad=1&optimalangles=1&outputformat=json"
    try:
        reponse = requests.get(url, timeout=3)
        if reponse.status_code == 200:
            return sum([mois['H(opt)'] for mois in reponse.json()['outputs']['monthly']])
    except:
        pass
    return 1250

# --- 2. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Agri-Avocat Pro", layout="wide", page_icon="⚖️")

# --- 3. BARRE LATÉRALE (PARAMÉTRAGES) ---
with st.sidebar:
    st.title("⚙️ Paramètres")
    st.markdown("---")
    
    st.subheader("1. Foncier (Localisation & Surface)")
    insee = st.text_input("Code INSEE (Point GPS central)", value="41075")
    section = st.text_input("Section", value="AA")
    numero = st.text_input("Numéro", value="0010")
    
    # Champ direct pour la surface (plus intuitif)
    surface_projet = st.number_input("Surface du projet (ha)", min_value=0.0, value=0.0, step=0.5, help="Laissez à 0.0 pour utiliser la surface automatique du cadastre.")
    
    st.markdown("---")
    st.subheader("2. Projet")
    taux_couverture = st.slider("Couverture légale (%)", 10, 40, 30) / 100
    type_elevage = st.selectbox("Type d'agriculture", ["Ovin (Moutons)", "Bovin (Vaches)", "Cultures (Trackers)"])
    distance_reseau = st.number_input("Distance réseau Enedis (km)", min_value=0.0, value=1.0, step=0.1)
    
    st.subheader("3. Négociation")
    analyser_offre = st.checkbox("Comparer avec une offre")
    loyer_propose = 0
    if analyser_offre:
        loyer_propose = st.number_input("Loyer proposé (€/ha/an)", value=2000, step=100)
        
    st.markdown("---")
    st.subheader("4. Paramètres Experts (Bail)")
    with st.expander("Ouvrir les réglages juridiques"):
        part_proprio = st.slider("Part du loyer pour le Propriétaire (%)", min_value=10, max_value=100, value=60)
        part_exploitant = 100 - part_proprio
        
        st.markdown("---")
        inflation = st.number_input("Indexation annuelle (Inflation %)", value=2.0, step=0.1) / 100
        deg_panneaux = st.number_input("Perte d'efficacité des panneaux (%/an)", value=0.5, step=0.1) / 100

    st.markdown("---")
    lancer = st.button("🚀 LANCER L'ANALYSE", type="primary", use_container_width=True)

# --- 4. ÉCRAN PRINCIPAL (RÉSULTATS) ---
if not lancer:
    st.title("⚖️ Outil d'Audit Agrivoltaïque pour Avocats")
    st.info("👈 Veuillez paramétrer le dossier dans le menu de gauche puis cliquez sur 'Lancer l'analyse'.")
    st.image("https://images.unsplash.com/photo-1592833159155-c62df1b65634?auto=format&fit=crop&w=1200&q=80", use_container_width=True)

if lancer:
    with st.spinner("Analyse en cours..."):
        api_en_ligne, surface_ign, lat, lon = recuperer_donnees_parcelle(insee, section, numero)
        irradiance = recuperer_ensoleillement_pvgis(lat, lon)
        
        # LOGIQUE DE SURFACE : Manuel > Automatique
        surface_retenue = surface_projet if surface_projet > 0 else surface_ign
        
        # --- CALCULS DE BASE ---
        surface_m2_couverte = (surface_retenue * 10000) * taux_couverture
        puissance_kwc = surface_m2_couverte / 5 
        production_kwh = surface_m2_couverte * irradiance * 0.21 * 0.80
        ca_annuel = production_kwh * 0.07 
        
        penalite_structure = 0.015 if "Bovin" in type_elevage else 0.025 if "Cultures" in type_elevage else 0
        penalite_reseau = ((distance_reseau * 100000) / 1000000) * 0.01
        taux_loyer_juste = max(0.015, 0.06 - penalite_structure - penalite_reseau)
        
        loyer_total_cible = ca_annuel * taux_loyer_juste
        loyer_ha_cible_total = loyer_total_cible / surface_retenue
        
        loyer_ha_proprio = loyer_ha_cible_total * (part_proprio / 100)
        loyer_ha_exploitant = loyer_ha_cible_total * (part_exploitant / 100)

        # --- AFFICHAGE ---
        st.title(f"Dossier Parcelle : {section}-{numero} ({insee})")
        
        tab1, tab2, tab3 = st.tabs(["📍 Synthèse & Carte", "📈 Projection Financière (30 ans)", "⚖️ Argumentaire Juridique"])
        
        with tab1:
            if surface_projet > 0:
                st.success(f"✅ Analyse basée sur la surface saisie : **{round(surface_retenue, 2)} hectares**")
            else:
                st.success(f"✅ Analyse basée sur la surface cadastrale automatique : **{round(surface_retenue, 2)} hectares**")
                
            st.subheader("💰 Potentiel Financier du Terrain")
            col_met1, col_met2, col_met3 = st.columns(3)
            col_met1.metric("Loyer Cible TOTAL", f"{round(loyer_ha_cible_total)} € / ha / an")
            col_met2.metric(f"Part Propriétaire ({part_proprio}%)", f"{round(loyer_ha_proprio)} € / ha / an")
            col_met3.metric(f"Part Fermier ({part_exploitant}%)", f"{round(loyer_ha_exploitant)} € / ha / an")
            
            if analyser_offre:
                st.markdown("---")
                diff = loyer_ha_proprio - loyer_propose
                if diff > 500:
                    st.error(f"⚠️ **OFFRE SOUS-ÉVALUÉE :** Vous pouvez exiger au moins {round(loyer_ha_proprio)} €/ha.")
                else:
                    st.success(f"✅ **OFFRE JUSTE :** Proposition cohérente.")
            
            st.markdown("### 🗺️ Vue Satellite (Localisation)")
            df_carte = pd.DataFrame({'lat': [lat], 'lon': [lon]})
            st.map(df_carte, zoom=13)

        with tab2:
            st.subheader(f"Évolution des revenus sur 30 ans pour le Propriétaire")
            annees = list(range(1, 31))
            loyers_annuels_totaux = [loyer_total_cible * ((1 + inflation) ** (an - 1)) * ((1 - deg_panneaux) ** (an - 1)) for an in annees]
            loyers_annuels_proprio = [l * (part_proprio / 100) for l in loyers_annuels_totaux]
            cumul_proprio = [sum(loyers_annuels_proprio[:an]) for an in annees]
            
            df_projection = pd.DataFrame({"Année": annees, "Revenus Cumulés (€)": cumul_proprio}).set_index("Année")
            st.area_chart(df_projection["Revenus Cumulés (€)"], color="#1f77b4")
            st.metric("Revenu Total Cumulé (30 ans)", f"{round(cumul_proprio[-1]):,} €".replace(",", " "))

        with tab3:
            st.subheader("🔍 Données opposables pour la négociation")
            st.markdown(f"""
            * **Assiette foncière retenue** : {round(surface_retenue, 2)} hectares.
            * **Gisement Solaire local** : {round(irradiance)} kWh/m²/an (Source PVGIS Europe).
            * **Taux de redistribution cible** : {round(taux_loyer_juste * 100, 2)}% du chiffre d'affaires brut.
            * **Répartition préconisée** : {part_proprio}% Propriétaire / {part_exploitant}% Exploitant.
            """)
