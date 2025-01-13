class WrongUserInputException extends Error {
	constructor(message, errorCode) {
		super(message);
		this.name = 'WrongUserInputException';
		this.errorCode = errorCode
	}
}

class DevException extends Error {
	constructor(message) {
		super(message);
		this.name = 'DevException'
	}
}

class PeerException extends Error {
	constructor(message, errorCode) {
		super(message);
		this.name = 'PeerException';
		this.errorCode = errorCode
	}
}

class TemporaryException extends Error {
	constructor(message) {
		super(message);
		this.name = 'TemporaryException'
	}
}

function AssertDev(condition, message) {
    if (!condition) {
        throw new DevException(message);
    }
}

function AssertUser(condition, message, errorCode) {
    if (!condition) {
        throw new WrongUserInputException(message, errorCode);
    }
}

function AssertPeer(condition, message, errorCode) {
    if (!condition) {
        throw new PeerException(message, errorCode);
    }
}

function TemporaryError(condition, message) {
    if (!condition) {
        throw new TemporaryException(message);
    }
}

module.exports = {
	WrongUserInputException,
	DevException,
	PeerException,
	TemporaryException,
	AssertDev,
    AssertUser,
    AssertPeer,
    TemporaryError,
};