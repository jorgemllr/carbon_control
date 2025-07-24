// Inicializa el mapa con un zoom predeterminado
var map = L.map('map').setView([20.588844, -100.389888], 4);

// Mapa oscuro con toques púrpura (usando Thunderforest)
L.tileLayer('https://api.maptiler.com/maps/streets-v2-dark/{z}/{x}/{y}.png?key=hAu1zgevGSOfDmhCieqY', {
    maxZoom: 18,
    attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>'
}).addTo(map);

// Muestra la latitud y longitud actuales en los menús
map.on('mousemove', function (e) {
    document.getElementById('lat').textContent = e.latlng.lat.toFixed(5);
    document.getElementById('lon').textContent = e.latlng.lng.toFixed(5);
});

// Almacena los marcadores existentes
var markers = [];

// Función para buscar ubicaciones
function searchLocation() {
    var query = document.getElementById('search-bar').value.trim();
    var errorElement = document.getElementById('search-error'); // Asegúrate de tener este elemento en tu HTML

    if (query) {
        // Limpiar mensaje de error si existe
        if (errorElement) {
            errorElement.classList.remove('search-error-visible', 'search-error-shake');
        }

        var url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`;

        // Mostrar loader (opcional)
        toggleSearchLoading(true);

        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data && data.length > 0) {
                    var firstResult = data[0];
                    var lat = firstResult.lat;
                    var lon = firstResult.lon;

                    map.setView([lat, lon], 13);

                    // Limpiar marcadores
                    clearMarkers();

                    // Agregar nuevo marcador
                    addNewMarker(lat, lon, firstResult.display_name);
                } else {
                    showSearchMessage('🌍 No encontramos esa ciudad. Intenta con otro nombre', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showSearchMessage('⚠️ Error al conectar con el servidor', 'error');
            })
            .finally(() => {
                toggleSearchLoading(false);
                hideSuggestions();
            });
    } else {
        // Mostrar error en la interfaz
        if (errorElement) {
            errorElement.textContent = '🌍 Por favor, ingresa una ciudad';
            errorElement.classList.add('search-error-visible', 'search-error-shake');
            setTimeout(() => errorElement.classList.remove('search-error-shake'), 500);
        }

        // Opcional: Enfocar el input automáticamente
        document.getElementById('search-bar').focus();
    }
}

// Funciones auxiliares (añádelas a tu código)
function toggleSearchLoading(show) {
    var icon = document.querySelector('.search-icon');
    if (icon) {
        icon.classList.toggle('fa-search', !show);
        icon.classList.toggle('fa-spinner', show);
        icon.classList.toggle('fa-spin', show);
    }
}

function showSearchMessage(message, type) {
    var errorElement = document.getElementById('search-error');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.className = type === 'error' ? 'search-error-visible' : '';
        if (type === 'error') {
            errorElement.classList.add('search-error-shake');
            setTimeout(() => errorElement.classList.remove('search-error-shake'), 500);
        }
    }
}

function clearMarkers() {
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
}

function addNewMarker(lat, lon, name) {
    var newMarker = L.marker([lat, lon]).addTo(map);
    newMarker.bindPopup(`<b>${name}</b>`).openPopup();
    markers.push(newMarker);
}

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
