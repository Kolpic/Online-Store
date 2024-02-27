function solve(n, a, b, c) {
    let pointsFromA = [];
    pointsFromA.push(0);
    let pointsFromY = [];
    let totalRedLength = 0;

    for (let i = a; i <= n; i += a) {
        pointsFromA.push(i);
    }

    pointsFromY.push(n)
    for (let j = b; j <= n; j += b) {
        pointsFromY.push(n - j);
    }

    pointsFromA.forEach(pointA => {
        if (pointsFromY.includes(pointA - c)) {
            totalRedLength += c;
        }

        if (pointsFromY.includes(pointA + c)) {
            totalRedLength += c;
        }
    });

    let unpaintedLength = (n - totalRedLength);

    console.log(unpaintedLength);
    return unpaintedLength;
}

solve(10, 2, 3, 1);