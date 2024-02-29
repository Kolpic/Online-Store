function visualize() {
    const n = parseInt(document.getElementById('lengthN').value);
    const a = parseInt(document.getElementById('intervalA').value);
    const b = parseInt(document.getElementById('intervalB').value);
    const c = parseInt(document.getElementById('distanceC').value);
    const visualization = document.getElementById('visualization');

    visualization.innerHTML = '';

    for (let i = 0; i <= n; i += a) {
        addPoint(i, n, 'A');
    }

    for (let j = 0; j <= n; j += b) {
        addPoint(n - j, n, 'B');
    }

    let lineCounter = 0;
    for (let pointA = 0; pointA <= n; pointA += a) {
        for (let pointY = 0; pointY <= n; pointY += b) {
            let distance = Math.abs(pointA - (n - pointY));
            if (distance === c) {
                addRedLine(Math.min(pointA, n - pointY), c, n);
                lineCounter++;
            }
        }
    }

    let result = n - lineCounter;
    document.getElementById('result').textContent = `Unpainted Length: ${result} meters`; 
}

function addPoint(position, totalLength, type) {
    const point = document.createElement('div');
    point.className = type === 'A' ? 'pointA' : 'pointB';
    point.style.left = `${(position / totalLength) * 100}%`;
    document.getElementById('visualization').appendChild(point);
}

function addRedLine(position, length, totalLength) {
    const line = document.createElement('div');
    line.className = 'red-line';
    line.style.left = `${(position / totalLength) * 100}%`;
    line.style.width = `${(length / totalLength) * 100}%`;
    document.getElementById('visualization').appendChild(line);
}  
  
