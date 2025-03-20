// Inicializa el mapa con un zoom predeterminado
var map = L.map('map').setView([20.626898, -100.187538], 17);

// Agrega una capa de mapa satelital de Esri
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://www.esri.com/en-us/home">Esri</a>',
}).addTo(map);

// Función para obtener la ubicación actual del usuario
function getCurrentLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function (position) {
            var lat = position.coords.latitude;
            var lon = position.coords.longitude;

            // Centra el mapa en la ubicación actual
            map.setView([lat, lon], 17);

            // Agrega un marcador en la ubicación actual
            var marker = L.marker([lat, lon]).addTo(map);

            // Contenido del popup
            var popupContent = "<b>Current Location</b><br>" +
                "Your current position: " + lat.toFixed(5) + ", " + lon.toFixed(5) + "<br>" +
                "This is a notice about your location.";

            marker.bindPopup(popupContent, { minWidth: 200 }).openPopup(); // Ajusta minWidth según sea necesario
        }, function () {
            alert("Error al obtener la ubicación. Asegúrate de que la geolocalización esté habilitada.");
        });
    } else {
        alert("La geolocalización no es compatible con este navegador.");
    }
}

// Llama a la función para obtener la ubicación al cargar la página
getCurrentLocation();

// Muestra la latitud y longitud actuales en los menús
map.on('mousemove', function (e) {
    document.getElementById('lat').textContent = e.latlng.lat.toFixed(5);
    document.getElementById('lon').textContent = e.latlng.lng.toFixed(5);
});

// Almacena los marcadores existentes
var markers = [];

// Función para buscar ubicaciones
function searchLocation() {
    var query = document.getElementById('search-bar').value;
    if (query) {
        var url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data && data.length > 0) {
                    var firstResult = data[0];
                    var lat = firstResult.lat;
                    var lon = firstResult.lon;

                    // Centra el mapa en la nueva ubicación
                    map.setView([lat, lon], 13);

                    // Limpia los marcadores existentes
                    markers.forEach(marker => map.removeLayer(marker));
                    markers = [];

                    // Agrega un nuevo marcador
                    var newMarker = L.marker([lat, lon]).addTo(map);
                    newMarker.bindPopup(`<b>${firstResult.display_name}</b>`).openPopup();
                    markers.push(newMarker);
                } else {
                    alert('No se encontraron resultados.');
                }
                hideSuggestions(); // Oculta sugerencias después de buscar
            })
            .catch(error => {
                console.error('Error:', error);
            });
    } else {
        alert('Por favor, ingresa un término de búsqueda.');
    }
}

// Resto del código permanece igual...

// Función para mostrar sugerencias
function showSuggestions(suggestions) {
    const suggestionsContainer = document.getElementById('suggestions');
    suggestionsContainer.innerHTML = ''; // Limpia las sugerencias anteriores
    suggestions.forEach(suggestion => {
        const div = document.createElement('div');
        div.textContent = suggestion.display_name;
        div.onclick = () => {
            document.getElementById('search-bar').value = suggestion.display_name;
            searchLocation();
        };
        suggestionsContainer.appendChild(div);
    });
    suggestionsContainer.style.display = suggestions.length > 0 ? 'block' : 'none'; // Muestra u oculta el contenedor
}

// Función para buscar sugerencias (con debounce)
function getSuggestions() {
    const query = document.getElementById('search-bar').value;
    if (query) {
        var url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                showSuggestions(data); // Muestra las sugerencias
            })
            .catch(error => {
                console.error('Error:', error);
            });
    } else {
        hideSuggestions();
    }
}

// Función para ocultar sugerencias
function hideSuggestions() {
    const suggestionsContainer = document.getElementById('suggestions');
    suggestionsContainer.style.display = 'none'; // Oculta el contenedor de sugerencias
}

// Función de debounce para limitar las llamadas a la API
function debounce(func, delay) {
    let debounceTimer;
    return function () {
        const context = this;
        const args = arguments;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => func.apply(context, args), delay);
    };
}

// Agregar eventos
document.getElementById('search-bar').addEventListener('input', debounce(getSuggestions, 300));
document.getElementById('search-bar').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        searchLocation();
    }
});

// Crear contenedor de sugerencias
const suggestionsContainer = document.createElement('div');
suggestionsContainer.id = 'suggestions';
suggestionsContainer.style.position = 'absolute'; // Estilo para el posicionamiento
suggestionsContainer.style.backgroundColor = 'white'; // Fondo blanco
suggestionsContainer.style.border = '1px solid #ccc'; // Borde
suggestionsContainer.style.zIndex = '500'; // Asegurarse de que no esté encima del mapa
suggestionsContainer.style.maxHeight = '150px'; // Limita el alto para evitar que cubra mucho espacio
suggestionsContainer.style.overflowY = 'scroll'; // Permite desplazarse si hay muchas sugerencias
document.getElementById('container').appendChild(suggestionsContainer);

// Manejo del chatbot
function sendMessage() {
    const userInput = document.getElementById('pford-chat-input').value;
    if (userInput) {
        fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ user_input: userInput })
        })
            .then(response => response.json())
            .then(data => {
                // Actualiza el mensaje de Pford con la respuesta del chatbot
                document.getElementById('pford-message').textContent = data.response;

                // Llama a MathJax para procesar cualquier fórmula en LaTeX
                if (typeof MathJax !== 'undefined') {
                    MathJax.typeset();
                }

                // Limpia el input
                document.getElementById('pford-chat-input').value = '';
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }
}

// Agregar evento para detectar el clic en el botón
document.getElementById('pford-chat-button').addEventListener('click', sendMessage);

// Agregar evento para detectar la tecla Enter
document.getElementById('pford-chat-input').addEventListener('keypress', function (event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
});