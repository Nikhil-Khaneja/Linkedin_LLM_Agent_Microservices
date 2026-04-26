const router = require('express').Router();
const { getDB } = require('../db/mysql');
const { requireAuth } = require('../middleware/auth');
const { AppError } = require('../middleware/errorHandler');
const { publishEvent } = require('../kafka/producer');

const CONTRACT_COMPANY_SIZES = ['startup', 'small', 'medium', 'large', 'enterprise'];
const CONTRACT_ACCESS_LEVELS = ['admin', 'recruiter', 'reviewer'];

function isValidRecruiterId(value) {
  return typeof value === 'string' && /^rec_[A-Za-z0-9_]+$/.test(value);
}

function isValidCompanyId(value) {
  return typeof value === 'string' && /^cmp_[A-Za-z0-9_]+$/.test(value);
}

function normalizeEmail(email) {
  return String(email || '').trim().toLowerCase();
}

function validateString(value, min, max) {
  return typeof value === 'string' && value.trim().length >= min && value.trim().length <= max;
}

function splitName(name) {
  const trimmed = String(name || '').trim().replace(/\s+/g, ' ');
  if (!trimmed) {
    return { firstName: '', lastName: '' };
  }
  const parts = trimmed.split(' ');
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: '' };
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(' ')
  };
}

function toDbCompanySize(contractSize) {
  const map = {
    startup: '1-10',
    small: '11-50',
    medium: '51-200',
    large: '201-500',
    enterprise: '5000+'
  };
  return map[contractSize] || '51-200';
}

function fromDbCompanySize(dbSize) {
  const map = {
    '1-10': 'startup',
    '11-50': 'small',
    '51-200': 'medium',
    '201-500': 'large',
    '501-1000': 'large',
    '1001-5000': 'enterprise',
    '5000+': 'enterprise'
  };
  return map[dbSize] || 'medium';
}

function toDbAccessLevel(contractAccessLevel) {
  const map = {
    admin: 'admin',
    recruiter: 'standard',
    reviewer: 'viewer'
  };
  return map[contractAccessLevel] || 'standard';
}

function fromDbAccessLevel(dbAccessLevel) {
  const map = {
    admin: 'admin',
    standard: 'recruiter',
    viewer: 'reviewer'
  };
  return map[dbAccessLevel] || 'recruiter';
}

function buildRecruiterResponse(row) {
  return {
    recruiter_id: row.recruiter_id,
    name: `${row.first_name || ''} ${row.last_name || ''}`.trim(),
    email: row.email,
    phone: row.phone,
    company_id: row.company_id,
    company_name: row.company_name,
    company_industry: row.company_industry,
    company_size: fromDbCompanySize(row.company_size),
    access_level: fromDbAccessLevel(row.access_level),
    status: row.is_deleted ? 'inactive' : 'active'
  };
}

async function getRecruiterById(db, recruiterId) {
  const [rows] = await db.execute(
    `
      SELECT
        r.recruiter_id,
        r.user_id,
        r.company_id,
        r.first_name,
        r.last_name,
        r.email,
        r.phone,
        r.access_level,
        r.is_deleted,
        c.company_name,
        c.company_industry,
        c.company_size
      FROM recruiters r
      LEFT JOIN companies c ON c.company_id = r.company_id
      WHERE r.recruiter_id = ? AND r.is_deleted = 0
      LIMIT 1
    `,
    [recruiterId]
  );

  return rows[0] || null;
}

async function getRecruiterByUserId(db, userId) {
  const [rows] = await db.execute(
    `
      SELECT
        r.recruiter_id,
        r.user_id,
        r.company_id,
        r.first_name,
        r.last_name,
        r.email,
        r.phone,
        r.access_level,
        r.is_deleted,
        c.company_name,
        c.company_industry,
        c.company_size
      FROM recruiters r
      LEFT JOIN companies c ON c.company_id = r.company_id
      WHERE r.user_id = ? AND r.is_deleted = 0
      LIMIT 1
    `,
    [userId]
  );

  return rows[0] || null;
}

async function getCompanyById(db, companyId) {
  const [rows] = await db.execute(
    `
      SELECT
        company_id,
        company_name,
        company_industry,
        company_size
      FROM companies
      WHERE company_id = ?
      LIMIT 1
    `,
    [companyId]
  );

  return rows[0] || null;
}

function ensureRecruiterOrAdmin(req, next) {
  const isRecruiter = req.user.userType === 'recruiter';
  const isAdmin = req.user.role === 'admin';

  if (!isRecruiter && !isAdmin) {
    return next(
      new AppError(
        403,
        'forbidden',
        'Authenticated user lacks permission for recruiter actions.',
        false
      )
    );
  }

  return true;
}

router.post('/create', requireAuth, async (req, res, next) => {
  try {
    if (!ensureRecruiterOrAdmin(req, next)) {
      return;
    }

    const {
      recruiter_id,
      company_id,
      name,
      email,
      phone,
      company_name,
      company_industry,
      company_size,
      access_level
    } = req.body || {};

    const details = {};

    if (!isValidRecruiterId(recruiter_id)) {
      details.recruiter_id = 'invalid_format';
    }

    if (company_id !== undefined && company_id !== null && company_id !== '' && !isValidCompanyId(company_id)) {
      details.company_id = 'invalid_format';
    }

    if (!validateString(name, 1, 120)) {
      details.name = 'out_of_range';
    }

    if (!validateString(email, 3, 254) || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email))) {
      details.email = 'invalid_format';
    }

    if (phone !== undefined && phone !== null && String(phone).length > 24) {
      details.phone = 'out_of_range';
    }

    if (!validateString(company_name, 1, 160)) {
      details.company_name = 'out_of_range';
    }

    if (company_industry !== undefined && company_industry !== null && String(company_industry).length > 80) {
      details.company_industry = 'out_of_range';
    }

    if (company_size !== undefined && company_size !== null && !CONTRACT_COMPANY_SIZES.includes(company_size)) {
      details.company_size = 'invalid_enum';
    }

    if (!CONTRACT_ACCESS_LEVELS.includes(access_level)) {
      details.access_level = 'invalid_enum';
    }

    if (Object.keys(details).length > 0) {
      return next(
        new AppError(
          400,
          'validation_error',
          'One or more request fields are invalid.',
          false,
          details
        )
      );
    }

    const db = getDB();
    const normalizedEmail = normalizeEmail(email);

    const [existingEmailRows] = await db.execute(
      `
        SELECT recruiter_id
        FROM recruiters
        WHERE LOWER(email) = ?
        LIMIT 1
      `,
      [normalizedEmail]
    );

    if (existingEmailRows.length > 0) {
      return next(
        new AppError(
          409,
          'duplicate_recruiter_email',
          'A recruiter with this email already exists.',
          false,
          {}
        )
      );
    }

    const [existingRecruiterRows] = await db.execute(
      `
        SELECT recruiter_id
        FROM recruiters
        WHERE recruiter_id = ?
        LIMIT 1
      `,
      [recruiter_id]
    );

    if (existingRecruiterRows.length > 0) {
      return next(
        new AppError(
          409,
          'validation_error',
          'Recruiter ID already exists.',
          false,
          { recruiter_id: 'already_exists' }
        )
      );
    }

    const [existingUserRows] = await db.execute(
      `
        SELECT recruiter_id
        FROM recruiters
        WHERE user_id = ?
        LIMIT 1
      `,
      [req.user.userId]
    );

    if (existingUserRows.length > 0) {
      return next(
        new AppError(
          403,
          'forbidden',
          'Authenticated recruiter already has a recruiter profile.',
          false,
          {}
        )
      );
    }

    let resolvedCompanyId = company_id || null;

    if (resolvedCompanyId) {
      const existingCompany = await getCompanyById(db, resolvedCompanyId);
      if (!existingCompany) {
        await db.execute(
          `
            INSERT INTO companies (
              company_id,
              company_name,
              company_industry,
              company_size
            ) VALUES (?, ?, ?, ?)
          `,
          [
            resolvedCompanyId,
            String(company_name).trim(),
            company_industry ? String(company_industry).trim() : null,
            toDbCompanySize(company_size || 'medium')
          ]
        );
      }
    } else {
      resolvedCompanyId = `cmp_${recruiter_id.slice(4)}`;
      const maybeExisting = await getCompanyById(db, resolvedCompanyId);

      if (!maybeExisting) {
        await db.execute(
          `
            INSERT INTO companies (
              company_id,
              company_name,
              company_industry,
              company_size
            ) VALUES (?, ?, ?, ?)
          `,
          [
            resolvedCompanyId,
            String(company_name).trim(),
            company_industry ? String(company_industry).trim() : null,
            toDbCompanySize(company_size || 'medium')
          ]
        );
      }
    }

    const { firstName, lastName } = splitName(name);

    await db.execute(
      `
        INSERT INTO recruiters (
          recruiter_id,
          user_id,
          company_id,
          first_name,
          last_name,
          email,
          phone,
          access_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `,
      [
        recruiter_id,
        req.user.userId,
        resolvedCompanyId,
        firstName,
        lastName,
        normalizedEmail,
        phone ? String(phone).trim() : null,
        toDbAccessLevel(access_level)
      ]
    );

    await publishEvent('recruiter.created', {
      trace_id: req.traceId,
      recruiter_id,
      company_id: resolvedCompanyId,
      user_id: req.user.userId,
      event_type: 'recruiter.created'
    });

    return res.status(201).json({
      success: true,
      trace_id: req.traceId,
      data: {
        recruiter_id,
        company_id: resolvedCompanyId,
        status: 'active'
      }
    });
  } catch (err) {
    return next(err);
  }
});

router.post('/get', requireAuth, async (req, res, next) => {
  try {
    if (!ensureRecruiterOrAdmin(req, next)) {
      return;
    }

    const { recruiter_id } = req.body || {};
    const db = getDB();

    let recruiter = null;

    if (recruiter_id !== undefined && recruiter_id !== null && recruiter_id !== '') {
      if (!isValidRecruiterId(recruiter_id)) {
        return next(
          new AppError(
            400,
            'validation_error',
            'One or more request fields are invalid.',
            false,
            { recruiter_id: 'invalid_format' }
          )
        );
      }

      recruiter = await getRecruiterById(db, recruiter_id);
    } else {
      recruiter = await getRecruiterByUserId(db, req.user.userId);
    }

    if (!recruiter) {
      return next(new AppError(404, 'not_found', 'Recruiter record not found.', false, {}));
    }

    const isOwner = recruiter.user_id === req.user.userId;
    const isAdmin = fromDbAccessLevel(recruiter.access_level) === 'admin' || req.user.role === 'admin';

    if (!isOwner && !isAdmin) {
      return next(
        new AppError(
          403,
          'forbidden',
          'Authenticated user lacks permission for the target recruiter.',
          false,
          {}
        )
      );
    }

    return res.json({
      success: true,
      trace_id: req.traceId,
      data: {
        recruiter: buildRecruiterResponse(recruiter)
      }
    });
  } catch (err) {
    return next(err);
  }
});

router.post('/update', requireAuth, async (req, res, next) => {
  try {
    if (!ensureRecruiterOrAdmin(req, next)) {
      return;
    }

    const {
      recruiter_id,
      name,
      phone,
      company_name,
      company_industry,
      company_size,
      access_level
    } = req.body || {};

    if (!isValidRecruiterId(recruiter_id)) {
      return next(
        new AppError(
          400,
          'validation_error',
          'One or more request fields are invalid.',
          false,
          { recruiter_id: 'invalid_format' }
        )
      );
    }

    const details = {};

    if (name !== undefined && !validateString(name, 1, 120)) {
      details.name = 'out_of_range';
    }

    if (phone !== undefined && phone !== null && String(phone).length > 24) {
      details.phone = 'out_of_range';
    }

    if (company_name !== undefined && !validateString(company_name, 1, 160)) {
      details.company_name = 'out_of_range';
    }

    if (company_industry !== undefined && company_industry !== null && String(company_industry).length > 80) {
      details.company_industry = 'out_of_range';
    }

    if (company_size !== undefined && !CONTRACT_COMPANY_SIZES.includes(company_size)) {
      details.company_size = 'invalid_enum';
    }

    if (access_level !== undefined && !CONTRACT_ACCESS_LEVELS.includes(access_level)) {
      details.access_level = 'invalid_enum';
    }

    if (Object.keys(details).length > 0) {
      return next(
        new AppError(
          400,
          'validation_error',
          'One or more request fields are invalid.',
          false,
          details
        )
      );
    }

    const db = getDB();
    const recruiter = await getRecruiterById(db, recruiter_id);

    if (!recruiter) {
      return next(new AppError(404, 'not_found', 'Recruiter record not found.', false, {}));
    }

    const isOwner = recruiter.user_id === req.user.userId;
    const requesterRole = req.user.role;
    const currentAccessLevel = fromDbAccessLevel(recruiter.access_level);
    const requesterIsAdmin = requesterRole === 'admin' || (isOwner && currentAccessLevel === 'admin');

    if (!isOwner && !requesterIsAdmin) {
      return next(
        new AppError(
          403,
          'forbidden',
          'Authenticated user lacks permission for the target recruiter.',
          false,
          {}
        )
      );
    }

    if (access_level !== undefined && !requesterIsAdmin) {
      return next(
        new AppError(
          403,
          'forbidden',
          'Only a recruiter admin can change company access levels.',
          false,
          {}
        )
      );
    }

    const recruiterUpdates = [];
    const recruiterValues = [];

    if (name !== undefined) {
      const { firstName, lastName } = splitName(name);
      recruiterUpdates.push('first_name = ?');
      recruiterValues.push(firstName);
      recruiterUpdates.push('last_name = ?');
      recruiterValues.push(lastName);
    }

    if (phone !== undefined) {
      recruiterUpdates.push('phone = ?');
      recruiterValues.push(phone ? String(phone).trim() : null);
    }

    if (access_level !== undefined) {
      recruiterUpdates.push('access_level = ?');
      recruiterValues.push(toDbAccessLevel(access_level));
    }

    if (recruiterUpdates.length > 0) {
      recruiterValues.push(recruiter_id);
      await db.execute(
        `UPDATE recruiters SET ${recruiterUpdates.join(', ')} WHERE recruiter_id = ?`,
        recruiterValues
      );
    }

    const companyUpdates = [];
    const companyValues = [];

    if (company_name !== undefined) {
      companyUpdates.push('company_name = ?');
      companyValues.push(String(company_name).trim());
    }

    if (company_industry !== undefined) {
      companyUpdates.push('company_industry = ?');
      companyValues.push(company_industry ? String(company_industry).trim() : null);
    }

    if (company_size !== undefined) {
      companyUpdates.push('company_size = ?');
      companyValues.push(toDbCompanySize(company_size));
    }

    if (companyUpdates.length > 0 && recruiter.company_id) {
      companyValues.push(recruiter.company_id);
      await db.execute(
        `UPDATE companies SET ${companyUpdates.join(', ')} WHERE company_id = ?`,
        companyValues
      );
    }

    await publishEvent('recruiter.updated', {
      trace_id: req.traceId,
      recruiter_id,
      company_id: recruiter.company_id,
      user_id: recruiter.user_id,
      event_type: 'recruiter.updated'
    });

    return res.json({
      success: true,
      trace_id: req.traceId,
      data: {
        recruiter_id,
        updated: true
      }
    });
  } catch (err) {
    return next(err);
  }
});

module.exports = router;