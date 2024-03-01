function findSegmentData(A) {
    if (A < 1) return [0, 0];

    let maxLength = 0;
    let lengths = new Set();

    for (let x1 = 0; x1 <= A; x1++) {
        for (let y1 = 0; y1 <= A; y1++) {
            for (let x2 = 0; x2 <= A; x2++) {
                for (let y2 = 0; y2 <= A; y2++) {
                    // Формула за изчисление - (x2 - x1)2 + (y2 - y1)2 цялото под корен
                    // Изключваме без хоризонталните и вертикалните отсечки, като x1 / y1 трябва да е различно от x2 / y2
                    if (x1 !== x2 && y1 !== y2) {
                        let dx = x2 - x1;
                        let dy = y2 - y1;
                        let lengthSquared = dx * dx + dy * dy; // Питагорова теорема (в случая а*а + а*а)
                        let length = Math.sqrt(lengthSquared); // Диагонал на квадрата корен от питагоровата теорема
                        if (Number.isInteger(length)) {
                            lengths.add(length);
                            if (length > maxLength) {
                                maxLength = length;  
                            }
                        }
                    }
                }
            }
        }
    }

    return [maxLength, lengths.size];
}

// console.log(findSegmentData(1)); 
console.log(findSegmentData(10)); 