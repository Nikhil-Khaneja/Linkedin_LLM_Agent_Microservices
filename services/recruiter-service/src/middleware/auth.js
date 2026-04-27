const jwt = require('jsonwebtoken');
const axios = require('axios');
const { createPublicKey } = require('crypto');
const { AppError } = require('./errorHandler');

let publicKeyPem = null;
let jwksFetched = false;

async function fetchPublicKey() {
  if (jwksFetched && publicKeyPem) {
    return publicKeyPem;
  }

  const jwksUrl =
    process.env.AUTH_SERVICE_JWKS_URL ||
    'http://auth-service:3001/.well-known/jwks.json';

  const { data } = await axios.get(jwksUrl, { timeout: 5000 });

  if (!data || !Array.isArray(data.keys) || data.keys.length === 0) {
    throw new Error('JWKS keyset is empty');
  }

  const jwk = data.keys[0];
  const keyObject = createPublicKey({
    key: {
      kty: jwk.kty,
      n: jwk.n,
      e: jwk.e
    },
    format: 'jwk'
  });

  publicKeyPem = keyObject.export({ type: 'pkcs1', format: 'pem' });
  jwksFetched = true;
  return publicKeyPem;
}

function mapRole(decoded) {
  return (
    decoded.role ||
    decoded.access_level ||
    decoded.accessLevel ||
    null
  );
}

function mapUserType(decoded) {
  return (
    decoded.type ||
    decoded.user_type ||
    decoded.userType ||
    decoded.subject_type ||
    decoded.subjectType ||
    null
  );
}

function requireAuth(req, res, next) {
  const header = req.headers.authorization;

  if (!header || !header.startsWith('Bearer ')) {
    return next(
      new AppError(
        401,
        'auth_required',
        'Bearer token is missing or invalid.',
        false,
        {}
      )
    );
  }

  const token = header.slice(7);

  (async () => {
    let pem;

    try {
      pem = await fetchPublicKey();
    } catch (err) {
      return next(
        new AppError(
          503,
          'dependency_unavailable',
          'Authentication key service is unavailable.',
          true,
          {}
        )
      );
    }

    try {
      const decoded = jwt.verify(token, pem, { algorithms: ['RS256'] });

      req.user = {
        userId: decoded.sub,
        userType: mapUserType(decoded),
        role: mapRole(decoded),
        raw: decoded
      };

      return next();
    } catch (err) {
      return next(
        new AppError(
          401,
          'auth_required',
          'Bearer token is missing or invalid.',
          false,
          {}
        )
      );
    }
  })().catch(next);
}

module.exports = { requireAuth };