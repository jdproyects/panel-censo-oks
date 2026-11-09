import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from supabase import create_client

st.set_page_config(page_title="Censo Distribuidora OKS", layout="wide")

# 1. CONEXIÓN A SUPABASE
SUPABASE_URL = "https://yvpenjvartfxgbtvokff.supabase.co"
SUPABASE_KEY = "sb_publishable_4avg5Jh0Ic5mPWgIPnlzCQ_8q9d3H4K"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. CARGAR CUADRÍCULAS GEOJSON (Caché eliminada para forzar lectura del nuevo archivo)
def cargar_cuadriculas():
    return gpd.read_file("cuadriculas_censo.geojson")

cuadriculas = cargar_cuadriculas()

# 3. TÍTULO Y FILTROS LATERALES
st.title("🗺️ Panel de Control - Censo CABA (Distribuidora OKS)")

st.sidebar.header("Filtros de Control")
gestor_sel = st.sidebar.selectbox("Gestor", ["Todos", "Gestor 1", "Gestor 2", "Gestor 3", "Gestor 4"])
cuadricula_sel = st.sidebar.number_input("Filtrar por Cuadrícula (1-120)", min_value=0, max_value=120, value=0)
ver_clientes_actuales = st.sidebar.checkbox("Mostrar Clientes Actuales (3.900)", value=True)
ver_nuevos_censados = st.sidebar.checkbox("Mostrar Nuevos PDV Censados", value=True)

# 4. CONSULTAR DATOS EN SUPABASE (Límite ampliado para traer a los 3.900 clientes)
response = supabase.table("censo_pdv").select("*").limit(5000).execute()
df_pdv = response.data

# Tarjetas KPI de resumen
total_actuales = sum(1 for p in df_pdv if p.get('es_cliente_actual'))
total_nuevos = sum(1 for p in df_pdv if not p.get('es_cliente_actual'))

col1, col2, col3 = st.columns(3)
col1.metric("Clientes Base (Excel)", f"{total_actuales:,}")
col2.metric("Nuevos PDV Censados", f"{total_nuevos:,}")
col3.metric("Total PDV Registrados", f"{len(df_pdv):,}")

# 5. CREAR MAPA BASE DE CABA (OpenStreetMap)
m = folium.Map(location=[-34.6037, -58.3816], zoom_start=12, tiles="OpenStreetMap")

# Dibujar las 120 Cuadrículas (Resaltar si se filtra una específica)
folium.GeoJson(
    cuadriculas,
    style_function=lambda feature: {
        'fillColor': '#ff7800' if feature['properties']['id_cuadricula'] == cuadricula_sel else '#3186cc',
        'color': 'black',
        'weight': 2 if feature['properties']['id_cuadricula'] == cuadricula_sel else 1,
        'fillOpacity': 0.25 if feature['properties']['id_cuadricula'] == cuadricula_sel else 0.05
    },
    tooltip=folium.GeoJsonTooltip(fields=['id_cuadricula'], aliases=['Sección:'])
).add_to(m)

# Graficar Puntos de Venta (Con forzado de tipos numéricos para evitar que se oculten)
colores_canal = {
    'KIOSCO': 'red',
    'AUTOSERVICIO': 'blue',
    'MAYORISTA': 'purple',
    'FERRETERIA': 'orange',
    'ALMACEN': 'green'
}

puntos_dibujados = 0

for pdv in df_pdv:
    try:
        lat = float(pdv['latitud'])
        lon = float(pdv['longitud'])
    except (TypeError, ValueError):
        continue  # Si la coordenada no es un número válido, salta al siguiente
    
    es_actual = pdv.get('es_cliente_actual', True)
    c_id = int(pdv.get('id_cuadricula', 0) or 0)
    gestor = str(pdv.get('gestor_asignado', ''))
    canal = str(pdv.get('tipo_pdv', 'OTRO'))
    color = colores_canal.get(canal, 'gray')

    # Aplicar Filtro de Cuadrícula (si está seleccionado)
    if cuadricula_sel > 0 and c_id != cuadricula_sel:
        continue

    # Aplicar Filtro de Gestor (si está seleccionado)
    if gestor_sel != "Todos" and gestor != gestor_sel:
        continue

    # Dibujar marcador en el mapa
    if es_actual:
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color=color,
            fill=True,
            fill_opacity=0.8,
            popup=f"Cliente: {pdv.get('codigo_cliente')}<br>Canal: {canal}<br>Cuadrícula: {c_id}"
        ).add_to(m)
        puntos_dibujados += 1
    else:
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color="green", icon="shopping-cart"),
            popup=f"<b>NUEVO CENSO</b><br>Gestor: {gestor}<br>Canal: {canal}<br>Cuadrícula: {c_id}"
        ).add_to(m)
        puntos_dibujados += 1

st.sidebar.info(f"📍 Puntos visibles en mapa: {puntos_dibujados}")

st_folium(m, width=1200, height=650)