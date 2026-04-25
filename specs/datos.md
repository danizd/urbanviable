Secciones censales — CNIG / IGN
https://www.ine.es/dyngs/DAB/index.htm?cid=1389
ubicacion: data/secciones_censales
Este contenido es la cartografía oficial de secciones censales en formato Shapefile (polígonos + atributos) publicada por el Instituto Nacional de Estadística, y constituye la base geoespacial del proyecto, ya que define las unidades territoriales (CUSEC) sobre las que se integran y cruzan todos los datos (renta, población, etc.); debe almacenarse en \etl\data\secciones como fuente de entrada cruda del ETL, desde donde se carga con GeoPandas, se filtra a Galicia, se reproyecta y se usa como capa principal para hacer joins con el resto de datasets antes de generar las teselas finales del mapa.



Renta — Atlas de Renta (INE)
https://www.ine.es/dynt3/inebase/index.htm?padre=12385&capsel=12384
ubicacion: data/renta.csv
Ese archivo CSV del Instituto Nacional de Estadística contiene los indicadores de renta (media y mediana) a nivel de sección censal, pero en un formato “largo” orientado a análisis estadístico, donde cada fila representa una combinación de sección, indicador y año, en lugar de una tabla directa lista para GIS; para usarlo en tu proyecto debes filtrar el indicador que te interese (por ejemplo, renta media por hogar), quedarte con el último periodo disponible, construir correctamente el código CUSEC concatenando municipio+distrito+sección, y reducir el dataset a una tabla simple cusec → renta, que luego podrás unir (join) con el shapefile de secciones censales dentro de tu ETL para generar las capas del mapa de calor.


Actividad económica / competencia
https://download.geofabrik.de/europe/spain/galicia.html
ubicacion: data/galicia-260424.osm.pbf
El archivo galicia-260424.osm.pbf es un volcado binario comprimido de todos los datos geoespaciales de OpenStreetMap para Galicia (carreteras, edificios, comercios, puntos de interés, etc.), distribuido por Geofabrik, que sirve como fuente cruda para enriquecer tu plataforma de Location Intelligence; debes guardarlo en tu carpeta de ETL (por ejemplo \etl\data\osm\), procesarlo con herramientas como pyrosm o osmium para extraer elementos relevantes (como tiendas, restaurantes o servicios), y luego agregarlos por sección censal (CUSEC) para generar métricas como densidad de negocios o nivel de competencia que puedas integrar en tu modelo y visualizar en el mapa de calor.



Cartografía vectorial por provincia del catastro
https://www.sedecatastro.gob.es/DescargaDatos/SECFormularioDescargas.aspx
ubicacion: etl\data\catastro\[provincia]
Datos catastrales por municipio, y cada uno viene en ZIPs separados por capas.