function drawLine() {
    var canvas = document.getElementById('canvas');
    var ctx = canvas.getContext('2d');

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    var x1 = document.getElementById('x1').value;
    var y1 = document.getElementById('y1').value;
    var x2 = document.getElementById('x2').value;
    var y2 = document.getElementById('y2').value;

    ctx.beginPath();
    ctx.moveTo(x1, y1); // Start point
    ctx.lineTo(x2, y2); // End point
    ctx.stroke(); // Execute the drawing
}
