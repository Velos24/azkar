const MainScene = new Phaser.Class({
    Extends: Phaser.Scene,
    initialize: function MainScene() {
        Phaser.Scene.call(this, { key: 'mainScene' });
    },

    preload: function () {
        this.load.image('background', 'assets/background.png');
        this.load.image('platform', 'assets/platform.png');
        this.load.image('rashed', 'assets/rashed.png');
        this.load.image('lamp', 'assets/lamp.png');
        this.load.image('powerup', 'assets/powerup.png');
        this.load.audio('jump', 'assets/jump.mp3');
        this.load.audio('powerup', 'assets/powerup.mp3');
        this.load.audio('lamp', 'assets/lamp.mp3');
    },

    create: function () {
        this.add.image(400, 300, 'background');

        this.platforms = this.physics.add.staticGroup();
        this.hiddenPlatforms = this.physics.add.staticGroup();
        this.powerUps = this.physics.add.staticGroup();

        this.platforms.create(400, 568, 'platform').setScale(2).refreshBody();

        this.platforms.create(600, 400, 'platform');
        this.platforms.create(50, 250, 'platform');
        this.platforms.create(750, 220, 'platform');

        this.hiddenPlatforms.create(400, 300, 'platform').setVisible(false);

        this.powerUps.create(750, 180, 'powerup');

        const savedX = localStorage.getItem('playerX');
        const savedY = localStorage.getItem('playerY');
        const savedEnergy = localStorage.getItem('lampEnergy');

        this.player = this.physics.add.sprite(savedX || 100, savedY || 450, 'rashed');
        this.player.setBounce(0.2);
        this.player.setCollideWorldBounds(true);

        if (savedEnergy) {
            this.lampEnergy = parseInt(savedEnergy);
        } else {
            this.lampEnergy = 100;
        }

        const lamp = this.add.sprite(this.player.x + 20, this.player.y, 'lamp');
        lamp.setScale(0.5);

        this.physics.add.collider(this.player, this.platforms);
        this.physics.add.collider(this.player, this.hiddenPlatforms);
        this.physics.add.overlap(this.player, this.powerUps, this.collectPowerUp, null, this);

        this.cursors = this.input.keyboard.createCursorKeys();
        this.spaceKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);

        this.energyText = this.add.text(16, 16, 'طاقة المصباح: ' + this.lampEnergy, { fontSize: '32px', fill: '#fff' });

        this.jumpSound = this.sound.add('jump');
        this.powerupSound = this.sound.add('powerup');
        this.lampSound = this.sound.add('lamp');

        this.time.addEvent({
            delay: 5000,
            callback: () => {
                localStorage.setItem('playerX', this.player.x);
                localStorage.setItem('playerY', this.player.y);
                localStorage.setItem('lampEnergy', this.lampEnergy);
            },
            loop: true
        });

        // Game Over condition
        this.time.addEvent({
            delay: 1000,
            callback: () => {
                if (this.player.y > 600) {
                    this.scene.start('gameOverScene');
                }
            },
            loop: true
        });

        // Win condition
        this.physics.add.overlap(this.player, this.platforms.create(750, 100, 'platform').setVisible(false), () => {
            localStorage.setItem('gameCompleted', 'true');
            this.scene.start('winScene');
        }, null, this);
    },

    update: function () {
        if (this.cursors.left.isDown) {
            this.player.setVelocityX(-160);
        } else if (this.cursors.right.isDown) {
            this.player.setVelocityX(160);
        } else {
            this.player.setVelocityX(0);
        }

        if (this.cursors.up.isDown && this.player.body.touching.down) {
            this.player.setVelocityY(-330);
            this.jumpSound.play();
        }

        if (Phaser.Input.Keyboard.JustDown(this.spaceKey)) {
            if (this.lampEnergy > 0) {
                this.hiddenPlatforms.children.iterate(function (child) {
                    child.setVisible(true);
                });
                this.lampEnergy -= 10;
                this.energyText.setText('طاقة المصباح: ' + this.lampEnergy);
                this.lampSound.play();
            }
        }

        if (Phaser.Input.Keyboard.JustUp(this.spaceKey)) {
            this.hiddenPlatforms.children.iterate(function (child) {
                child.setVisible(false);
            });
        }
    },

    collectPowerUp: function (player, powerUp) {
        powerUp.disableBody(true, true);
        this.lampEnergy = 100;
        this.energyText.setText('طاقة المصباح: ' + this.lampEnergy);
        this.powerupSound.play();
    }
});

const StartScene = new Phaser.Class({
    Extends: Phaser.Scene,
    initialize: function StartScene() {
        Phaser.Scene.call(this, { key: 'startScene' });
    },

    create: function () {
        this.add.text(250, 250, 'The Last Light of Qadim', { fontSize: '32px', fill: '#fff' });
        this.add.text(300, 300, 'اضغط على مفتاح المسافة للبدء', { fontSize: '24px', fill: '#fff' });

        this.spaceKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);
    },

    update: function () {
        if (Phaser.Input.Keyboard.JustDown(this.spaceKey)) {
            this.scene.start('mainScene');
        }
    }
});

const GameOverScene = new Phaser.Class({
    Extends: Phaser.Scene,
    initialize: function GameOverScene() {
        Phaser.Scene.call(this, { key: 'gameOverScene' });
    },

    create: function () {
        this.add.text(300, 250, 'انتهت اللعبة', { fontSize: '32px', fill: '#fff' });
        this.add.text(250, 300, 'اضغط على مفتاح المسافة لإعادة اللعب', { fontSize: '24px', fill: '#fff' });

        this.spaceKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);
    },

    update: function () {
        if (Phaser.Input.Keyboard.JustDown(this.spaceKey)) {
            this.scene.start('mainScene');
        }
    }
});

const WinScene = new Phaser.Class({
    Extends: Phaser.Scene,
    initialize: function WinScene() {
        Phaser.Scene.call(this, { key: 'winScene' });
    },

    create: function () {
        this.add.text(300, 250, 'لقد فزت!', { fontSize: '32px', fill: '#fff' });
        this.add.text(250, 300, 'اضغط على مفتاح المسافة للعب مرة أخرى', { fontSize: '24px', fill: '#fff' });

        this.spaceKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);

        const secretsSection = document.getElementById('secrets-section');
        secretsSection.classList.remove('hidden');
    },

    update: function () {
        if (Phaser.Input.Keyboard.JustDown(this.spaceKey)) {
            this.scene.start('mainScene');
        }
    }
});

const config = {
    type: Phaser.AUTO,
    width: 800,
    height: 600,
    parent: 'game-container',
    physics: {
        default: 'arcade',
        arcade: {
            gravity: { y: 300 },
            debug: false
        }
    },
    scene: [StartScene, MainScene, GameOverScene, WinScene]
};

const game = new Phaser.Game(config);
