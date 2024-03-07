function findSegmentDataOptimized(A) {
    if (A < 1) return [0, 0];

    let maxLength = 0;
    let lengths = new Set();

    let squares = new Set();
    for (let i = 1; i <= A * Math.sqrt(2); i++) {
        squares.add(i * i);
    }

    for (let dx = 1; dx <= A; dx++) {
        for (let dy = 1; dy <= A; dy++) {
            if (dx !== dy) {
                let lengthSquared = dx * dx + dy * dy;
                if (squares.has(lengthSquared)) {
                    let length = Math.sqrt(lengthSquared);
                    lengths.add(length);
                    if (length > maxLength) {
                        maxLength = length;
                    }
                }
            }
        }
    }

    return [maxLength, lengths.size];
}

console.log(findSegmentDataOptimized(20000));