const gameBoard = document.getElementById('game-board');
const ctx = gameBoard.getContext('2d');
const scoreElement = document.getElementById('score');
const startScreen = document.getElementById('start-screen');
const optionsScreen = document.getElementById('options-screen');
const gameOverScreen = document.getElementById('game-over-screen');
const startBtn = document.getElementById('start-btn');
const optionsBtn = document.getElementById('options-btn');
const backToMenuBtn = document.getElementById('back-to-menu-btn');
const playAgainBtn = document.getElementById('play-again-btn');
const difficultySelect = document.getElementById('difficulty');
const finalScoreElement = document.getElementById('final-score');

const gridSize = 20;
let snake = [{ x: 10, y: 10 }];
let food = {};
let direction = 'right';
let score = 0;
let speed = 200;
let gameOver = false;
let gameInterval;

const eatSound = new Audio('eat.mp3');
const gameOverSound = new Audio('game-over.mp3');

function setDifficulty() {
    const difficulty = difficultySelect.value;
    if (difficulty === 'easy') {
        speed = 200;
    } else if (difficulty === 'medium') {
        speed = 150;
    } else if (difficulty === 'hard') {
        speed = 100;
    }
}

function startGame() {
    startScreen.style.display = 'none';
    gameOverScreen.style.display = 'none';
    optionsScreen.style.display = 'none';
    snake = [{ x: 10, y: 10 }];
    direction = 'right';
    score = 0;
    scoreElement.textContent = `النتيجة: ${score}`;
    gameOver = false;
    setDifficulty();
    generateFood();
    gameInterval = setInterval(main, speed);
}

function main() {
    if (gameOver) {
        clearInterval(gameInterval);
        finalScoreElement.textContent = score;
        gameOverScreen.style.display = 'flex';
        gameOverSound.play();
        return;
    }

    clearBoard();
    drawFood();
    moveSnake();
    drawSnake();
    checkCollision();
}

function clearBoard() {
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, gameBoard.width, gameBoard.height);
}

function drawSnake() {
    ctx.fillStyle = '#00f';
    snake.forEach(segment => {
        ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize, gridSize);
        ctx.strokeStyle = '#fff';
        ctx.strokeRect(segment.x * gridSize, segment.y * gridSize, gridSize, gridSize);
    });
}

function moveSnake() {
    const head = { x: snake[0].x, y: snake[0].y };

    switch (direction) {
        case 'up':
            head.y--;
            break;
        case 'down':
            head.y++;
            break;
        case 'left':
            head.x--;
            break;
        case 'right':
            head.x++;
            break;
    }

    snake.unshift(head);

    if (head.x === food.x && head.y === food.y) {
        score++;
        scoreElement.textContent = `النتيجة: ${score}`;
        eatSound.play();
        generateFood();

        // Increase speed every 5 points
        if (score % 5 === 0) {
            speed *= 0.9;
            clearInterval(gameInterval);
            gameInterval = setInterval(main, speed);
        }
    } else {
        snake.pop();
    }
}

function generateFood() {
    food = {
        x: Math.floor(Math.random() * (gameBoard.width / gridSize)),
        y: Math.floor(Math.random() * (gameBoard.height / gridSize))
    };

    // Ensure food doesn't spawn on the snake
    while (snake.some(segment => segment.x === food.x && segment.y === food.y)) {
        food = {
            x: Math.floor(Math.random() * (gameBoard.width / gridSize)),
            y: Math.floor(Math.random() * (gameBoard.height / gridSize))
        };
    }
}

function drawFood() {
    ctx.fillStyle = '#f00';
    ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize, gridSize);
    ctx.strokeStyle = '#fff';
    ctx.strokeRect(food.x * gridSize, food.y * gridSize, gridSize, gridSize);
}

function checkCollision() {
    const head = snake[0];

    // Wall collision
    if (head.x < 0 || head.x * gridSize >= gameBoard.width || head.y < 0 || head.y * gridSize >= gameBoard.height) {
        gameOver = true;
    }

    // Self collision
    for (let i = 1; i < snake.length; i++) {
        if (head.x === snake[i].x && head.y === snake[i].y) {
            gameOver = true;
        }
    }
}

function changeDirection(event) {
    const keyPressed = event.key;
    const goingUp = direction === 'up';
    const goingDown = direction === 'down';
    const goingLeft = direction === 'left';
    const goingRight = 'right';

    if (keyPressed === 'ArrowUp' && !goingDown) {
        direction = 'up';
    } else if (keyPressed === 'ArrowDown' && !goingUp) {
        direction = 'down';
    } else if (keyPressed === 'ArrowLeft' && !goingRight) {
        direction = 'left';
    } else if (keyPressed === 'ArrowRight' && !goingLeft) {
        direction = 'right';
    }
}

startBtn.addEventListener('click', startGame);
playAgainBtn.addEventListener('click', startGame);

optionsBtn.addEventListener('click', () => {
    startScreen.style.display = 'none';
    optionsScreen.style.display = 'flex';
});

backToMenuBtn.addEventListener('click', () => {
    optionsScreen.style.display = 'none';
    startScreen.style.display = 'flex';
});

document.addEventListener('keydown', changeDirection);
