from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pydeck as pdk
import streamlit as st
from supabase import Client, create_client

# 1. Configuración de página (Siempre debe ser el primer comando)
st.set_page_config(page_title="Panel de Control OKS", layout="wide")

# ==========================================
# 🔒 PANTALLA DE LOGIN
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center;'>🔒 Acceso al Panel OKS</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)
            
            if submit:
                if usuario == "admin" and clave == "oks2026":
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Usuario o clave incorrectos")
    
    # Detiene la ejecución del script aquí si no está autenticado
    st.stop()


# ==========================================
# 🗺️ INICIO DEL PANEL DE CONTROL (APP PRINCIPAL)
# ==========================================
TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# 2. Credenciales de Supabase
URL = "https://yvpenjvartfxgbtvokff.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl2cGVuanZhcnRmeGdidHZva2ZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3Njc5MjksImV4cCI6MjEwODM0MzkyOX0.u3ueYgxSf7deS2HgUxR1OIe7xjz-g-hLWRLT3PIWhDY"
supabase: Client = create_client(URL, KEY)

COLORES = [
    [220, 38, 38],    # rojo
    [37, 99, 235],    # azul
    [22, 163, 74],    # verde
    [234, 88, 12],    # naranja
]

def traer_todo(construir_query, pagina=1000):
    filas, desde = [], 0
    while True:
        r = construir_query().range(desde, desde + pagina - 1).execute()
        filas.extend(r.data)
        if len(r.data) < pagina:
            break
        desde += pagina
    return filas

def a_hora_argentina(serie):
    return pd.to_datetime(serie, utc=True).dt.tz_convert(TZ)

# Botón para cerrar sesión
colA, colB = st.columns([8, 1])
with colA:
    st.title("🗺️ Panel de Control - Censo OKS")
with colB:
    if st.button("Salir 🚪"):
        st.session_state.autenticado = False
        st.rerun()

if st.button("🔄 Actualizar datos"):
    st.rerun()

# ==========================================
# SECCIÓN 1: TABLA Y MAPA DE PUNTOS CENSADOS
# ==========================================
st.header("📋 Puntos de Venta Censados (En Vivo)")

datos_censo = traer_todo(
    lambda: supabase.table("censo_prospectos")
    .select("*")
    .order("created_at", desc=True)
)

if datos_censo:
    df_censo = pd.DataFrame(datos_censo)

    if "created_at" in df_censo.columns:
        df_censo["created_at"] = a_hora_argentina(df_censo["created_at"])
        df_censo["fecha"] = df_censo["created_at"].dt.date

    df_censo = df_censo.dropna(subset=["latitud", "longitud"])
    df_censo = df_censo[
        (df_censo["latitud"].between(-35.5, -33.5)) & 
        (df_censo["longitud"].between(-60.0, -57.0))
    ]

    f1, f2, f3 = st.columns(3)

    if "fecha" in df_censo.columns and not df_censo.empty:
        rango = f1.date_input(
            "Fechas",
            value=(df_censo["fecha"].min(), df_censo["fecha"].max()),
        )
        if isinstance(rango, (tuple, list)) and len(rango) == 2:
            df_censo = df_censo[
                (df_censo["fecha"] >= rango[0]) & (df_censo["fecha"] <= rango[1])
            ]

    if "censista_id" in df_censo.columns:
        gestores_censo = sorted(df_censo["censista_id"].dropna().unique())
        sel_gestores = f2.multiselect("Gestores", gestores_censo)
        if sel_gestores:
            df_censo = df_censo[df_censo["censista_id"].isin(sel_gestores)]

    if "tipo_pdv" in df_censo.columns:
        tipos = sorted(df_censo["tipo_pdv"].dropna().unique())
        sel_tipos = f3.multiselect("Tipo de PDV", tipos)
        if sel_tipos:
            df_censo = df_censo[df_censo["tipo_pdv"].isin(sel_tipos)]

    st.metric("PDV censados (con los filtros aplicados)", len(df_censo))

    columnas_deseadas = [
        "created_at",
        "censista_id",
        "id_zona",
        "tipo_pdv",
        "direccion",
        "latitud",
        "longitud",
        "url_foto",
    ]
    columnas_presentes = [c for c in columnas_deseadas if c in df_censo.columns]
    df_mostrar = df_censo[columnas_presentes].copy()

    if "created_at" in df_mostrar.columns:
        df_mostrar["created_at"] = df_mostrar["created_at"].dt.strftime(
            "%d/%m/%Y %H:%M"
        )

    nombres_columnas = {
        "created_at": "Fecha/Hora",
        "censista_id": "Gestor",
        "id_zona": "Zona",
        "tipo_pdv": "Tipo PDV",
        "direccion": "Dirección Exacta",
        "latitud": "Coord Y (Lat)",
        "longitud": "Coord X (Lng)",
        "url_foto": "Link Foto",
    }
    df_mostrar = df_mostrar.rename(columns=nombres_columnas)

    config_columnas = {}
    if "Link Foto" in df_mostrar.columns:
        config_columnas["Link Foto"] = st.column_config.LinkColumn(
            "Foto", display_text="Ver foto"
        )

    st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
        column_config=config_columnas,
    )

    csv = df_mostrar.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 Descargar Reporte en Excel (CSV)",
        data=csv,
        file_name="Reporte_Censo_OKS.csv",
        mime="text/csv",
    )

    if not df_censo.empty:
        df_mapa = df_censo.copy()
        df_mapa["gestor"] = df_mapa["censista_id"]
        df_mapa["tipo"] = df_mapa["tipo_pdv"]
        df_mapa["dir"] = df_mapa.get("direccion", "")

        capa_pdv = pdk.Layer(
            "ScatterplotLayer",
            data=df_mapa,
            get_position=["longitud", "latitud"],
            get_fill_color=[220, 38, 38],
            get_line_color=[255, 255, 255],
            get_radius=5,  
            stroked=True,
            line_width_min_pixels=1,
            pickable=True,
        )
        st.subheader("Ubicación de los PDV nuevos")
        st.pydeck_chart(
            pdk.Deck(
                layers=[capa_pdv],
                initial_view_state=pdk.ViewState(
                    latitude=float(df_mapa["latitud"].mean()),
                    longitude=float(df_mapa["longitud"].mean()),
                    zoom=16,
                ),
                map_style="light",
                tooltip={"text": "{tipo}\n{dir}\n{gestor}"},
            )
        )
else:
    st.info("Aún no hay puntos censados. Esperando a los gestores...")

st.divider()

# ==========================================
# SECCIÓN 2: MAPA DE RASTREO SILENCIOSO
# ==========================================
st.header("📍 Rastreo de Gestores en Calle")

hoy = datetime.now(TZ).date()
dia = st.date_input("Día a ver", value=hoy, key="dia_rastreo")

inicio = datetime.combine(dia, time.min, tzinfo=TZ)
fin = inicio + timedelta(days=1)

datos_rastreo = traer_todo(
    lambda: supabase.table("rastreo_censistas")
    .select("*")
    .gte("created_at", inicio.isoformat())
    .lt("created_at", fin.isoformat())
    .order("created_at")
)

if datos_rastreo:
    df_r = pd.DataFrame(datos_rastreo)
    df_r = df_r.dropna(subset=["latitud", "longitud"])
    
    df_r = df_r[
        (df_r["latitud"].between(-35.5, -33.5)) & 
        (df_r["longitud"].between(-60.0, -57.0))
    ]

    if df_r.empty:
        st.warning("No hay registros de rastreo válidos para ese día.")
    else:
        df_r["created_at"] = a_hora_argentina(df_r["created_at"])
        df_r["hora"] = df_r["created_at"].dt.strftime("%H:%M:%S")

        gestores = sorted(df_r["censista_id"].unique())
        seleccion = st.multiselect(
            "Gestores", gestores, default=gestores, key="gestores_rastreo"
        )
        df_r = df_r[df_r["censista_id"].isin(seleccion)]

        if df_r.empty:
            st.warning("No hay recorridos para esa selección.")
        else:
            caminos, ultimas = [], []
            for gestor, sub in df_r.groupby("censista_id"):
                sub = sub.sort_values("created_at")
                color = COLORES[gestores.index(gestor) % len(COLORES)]

                coords = sub[["longitud", "latitud"]].values.tolist()
                if len(coords) > 1:
                    caminos.append(
                        {
                            "gestor": gestor,
                            "path": coords,
                            "color": color,
                        }
                    )

                ult = sub.iloc[-1]
                ultimas.append(
                    {
                        "gestor": gestor,
                        "longitud": ult["longitud"],
                        "latitud": ult["latitud"],
                        "hora": ult["hora"],
                        "color": color,
                    }
                )

            df_caminos = pd.DataFrame(caminos) if caminos else pd.DataFrame(columns=["gestor", "path", "color"])
            df_ultimas = pd.DataFrame(ultimas)

            df_puntos = df_r.copy()
            df_puntos["gestor"] = df_puntos["censista_id"]
            df_puntos["color"] = df_puntos["censista_id"].apply(
                lambda g: COLORES[gestores.index(g) % len(COLORES)]
            )

            layers_list = []

            if not df_caminos.empty:
                capa_linea = pdk.Layer(
                    "PathLayer",
                    data=df_caminos,
                    get_path="path",
                    get_color="color",
                    get_width=4,
                    width_units="pixels",
                    width_min_pixels=3,
                    pickable=True,
                )
                layers_list.append(capa_linea)
            else:
                st.info("ℹ️ Hay solo 1 registro de ubicación para este gestor. Camina unos metros más para que la app envíe el segundo punto y dibuje la línea de recorrido.")

            capa_puntos = pdk.Layer(
                "ScatterplotLayer",
                data=df_puntos,
                get_position=["longitud", "latitud"],
                get_fill_color="color",
                get_radius=3,
                pickable=True,
            )
            layers_list.append(capa_puntos)

            capa_ultima = pdk.Layer(
                "ScatterplotLayer",
                data=df_ultimas,
                get_position=["longitud", "latitud"],
                get_fill_color="color",
                get_line_color=[255, 255, 255],
                get_radius=8,
                stroked=True,
                line_width_min_pixels=2,
                pickable=True,
            )
            layers_list.append(capa_ultima)

            st.pydeck_chart(
                pdk.Deck(
                    layers=layers_list,
                    initial_view_state=pdk.ViewState(
                        latitude=float(df_r["latitud"].mean()),
                        longitude=float(df_r["longitud"].mean()),
                        zoom=16,
                    ),
                    map_style="light",
                    tooltip={"text": "{gestor}\n{hora}"},
                )
            )
            st.caption(
                "Línea = recorrido del día · punto grande = última posición conocida de cada gestor"
            )
else:
    st.info(
        "No hay datos de rastreo para ese día. (Se registran mientras los gestores usan la app)"
    )