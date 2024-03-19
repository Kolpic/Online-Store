function findShortestPath(n, circles) {
    // Функция за намиране на разстоянието между два центъра на окръжности - формула от интернет: евклидово разстояние, използвайки питагоровата теорема
    function distance(x1, y1, x2, y2) {
      return Math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2);
    }
  
    // Функция за проверка дали две окръжности имат точно две общи точки - формула от интернет
    function intersects(circle1, circle2) {
      const dist = distance(circle1.x, circle1.y, circle2.x, circle2.y); //  Разстоянието между центровете на двете окръжности
      return dist < (circle1.r + circle2.r) && dist > Math.abs(circle1.r - circle2.r); //  дали разстоянието между центровете на окръжностите е по-малко от сумата на радиусите (което би означавало, че се пресичат)
    }
  
    const graph = new Array(n);
    for (let i = 0; i < n; i++) {
      graph[i] = new Array(n).fill(false);
      for (let j = 0; j < n; j++) {
        if (i !== j && intersects(circles[i], circles[j])) { // Проверяваме дали текущата двойка окръжности (различни помежду си) се пресичат в точно две точки.
          graph[i][j] = true;
        }
      }
    }
  
    // BFS за намиране на най-късия път
    const queue = [{ vertex: 0, distance: 0 }]; // опашка за BFS, като започваме от първата окръжност с дистанция 0
    const visited = new Array(n).fill(false); // масив, който следи посетените върхове
    visited[0] = true;
  
    while (queue.length > 0) {
      const { vertex, distance } = queue.shift();
      if (vertex === n - 1) {
        return distance;
      }
  
      for (let i = 0; i < n; i++) {
        if (graph[vertex][i] && !visited[i]) {
          visited[i] = true;
          queue.push({ vertex: i, distance: distance + 1 });
        }
      }
    }
  
    return -1;
  }
  
  const n = 10;
  const circles = [
    { x: 4, y: 0, r: 2 },
    { x: 7, y: 7, r: 2 },
    { x: 9, y: 0, r: 2 },
    { x: 8, y: 2, r: 2 },
    { x: 4, y: 10, r: 2 },
    { x: 5, y: 8, r: 2 },
    { x: 10, y: 0, r: 2 },
    { x: 1, y: 7, r: 2 },
    { x: 7, y: 5, r: 2 },
    { x: 9, y: 5, r: 2 }
  ];
  
  console.log(findShortestPath(n, circles));
  