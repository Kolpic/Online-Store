class WrongUserInputException extends Error {
	constructor(message) {
		super(message);
		this.name = 'WrongUserInputException';
	}
}

class DevException extends Error {
	constructor(message) {
		super(message);
		this.name = 'DevException'
	}
}

class PeerException extends Error {
	constructor(message) {
		super(message);
		this.name = 'PeerException';
	}
}

module.exports = {
	WrongUserInputException,
	DevException,
	PeerException,
};