function fillRect() {
    // Create a new div element to represent the rectangle
    let rect = document.createElement('div');
    
    // Get user input values
    let x = document.getElementById('x').value;
    let y = document.getElementById('y').value;
    let width = document.getElementById('width').value;
    let height = document.getElementById('height').value;
    
    // Construct the style attribute string
    var styleAttribute = `position: absolute; left: ${x}px; top: ${y}px; width: ${width}px; height: ${height}px; background-color: blue;`;
    
    // Apply the style string to the rectangle
    rect.setAttribute('style', styleAttribute);

    // Append the rectangle to the drawing area
    document.getElementById('drawing-area').appendChild(rect);
}

function fillRect2() {
    // Create a new div element to represent the rectangle
    let rect = document.createElement('div');
    
    // Get user input values
    let x = document.getElementById('x').value;
    let y = document.getElementById('y').value;
    let width = document.getElementById('width').value;
    let height = document.getElementById('height').value;

    // Set styles to position and size the rectangle
    rect.style.position = 'absolute';
    rect.style.left = x + 'px';
    rect.style.top = y + 'px';
    rect.style.width = width + 'px';
    rect.style.height = height + 'px';
    rect.style.backgroundColor = 'blue';

    document.getElementById('drawing-area').appendChild(rect);
}

function fillRect3() {
    let drawingArea = document.getElementById('drawing-area');
    drawingArea.innerHTML = ''; 

    let x = parseInt(document.getElementById('x').value, 10);
    let y = parseInt(document.getElementById('y').value, 10);
    let width = parseInt(document.getElementById('width').value, 10);
    let height = parseInt(document.getElementById('height').value, 10);

    drawingArea.style.position = 'relative';

    for (let i = 0; i < height; i++) { // Rows
        for (let j = 0; j < width; j++) { // Cols
            const pixel = document.createElement('div');
            pixel.style.position = 'absolute';
            pixel.style.left = `${x + j}px`;
            pixel.style.top = `${y + i}px`;
            pixel.style.width = '1px';
            pixel.style.height = '1px';
            pixel.style.backgroundColor = 'black';
            drawingArea.appendChild(pixel);
        }
    }
}

function drawCircle() {
    const drawingArea = document.getElementById('drawing-area');
    drawingArea.innerHTML = '';

    const centerX = parseInt(document.getElementById('x').value, 10);
    const centerY = parseInt(document.getElementById('y').value, 10);
    const radius = parseInt(document.getElementById('radius').value, 10);

    const diameter = radius * 2;
    for (let y = -radius; y <= radius; y++) {
        for (let x = -radius; x <= radius; x++) {
            if (x*x + y*y <= radius*radius) {
                const pixel = document.createElement('div');
                pixel.style.position = 'absolute';
                pixel.style.left = `${centerX + x}px`;
                pixel.style.top = `${centerY + y}px`;
                pixel.style.width = '1px';
                pixel.style.height = '1px';
                pixel.style.backgroundColor = 'black';
                drawingArea.appendChild(pixel);
            }
        }
    }
}
