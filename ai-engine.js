/* ═══════════════════════════════════════════════════════════
   ARFM — AI ENGINE
   Autonomous Right to be Forgotten Manager
   Core AI Architecture: Analysis, Risk, Classification
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ─── ACCOUNT ANALYZER ─────────────────────────────────────────
const AccountAnalyzer = {
    CATEGORIES: {
        social: { label: 'Social Media', icon: '👥', risk: 0.8, domains: ['facebook.com', 'instagram.com', 'twitter.com', 'x.com', 'linkedin.com', 'pinterest.com', 'reddit.com', 'tiktok.com', 'snapchat.com', 'tumblr.com'] },
        messaging: { label: 'Messaging', icon: '💬', risk: 0.7, domains: ['discord.com', 'slack.com', 'telegram.org', 'whatsapp.com'] },
        commerce: { label: 'E-Commerce', icon: '🛒', risk: 0.9, domains: ['shopify.com', 'etsy.com', 'ebay.com', 'amazon.com', 'wish.com', 'aliexpress.com'] },
        finance: { label: 'Finance', icon: '💳', risk: 1.0, domains: ['paypal.com', 'stripe.com', 'venmo.com', 'cashapp.com', 'robinhood.com', 'coinbase.com'] },
        devtools: { label: 'Dev Tools', icon: '⚙️', risk: 0.3, domains: ['github.com', 'gitlab.com', 'bitbucket.org', 'vercel.com', 'netlify.com', 'heroku.com', 'digitalocean.com', 'figma.com'] },
        productiv: { label: 'Productivity', icon: '📋', risk: 0.4, domains: ['notion.so', 'trello.com', 'asana.com', 'clickup.com', 'monday.com', 'airtable.com', 'miro.com', 'linear.app'] },
        marketing: { label: 'Marketing', icon: '📢', risk: 0.85, domains: ['mailchimp.com', 'hubspot.com', 'salesforce.com', 'sendgrid.com', 'constantcontact.com'] },
        media: { label: 'Media/Content', icon: '🎬', risk: 0.5, domains: ['spotify.com', 'netflix.com', 'youtube.com', 'twitch.tv', 'medium.com', 'substack.com'] },
        cloud: { label: 'Cloud Storage', icon: '☁️', risk: 0.7, domains: ['dropbox.com', 'box.com', 'mega.nz', 'onedrive.com', 'icloud.com'] },
        education: { label: 'Education', icon: '🎓', risk: 0.3, domains: ['coursera.org', 'udemy.com', 'edx.org', 'skillshare.com', 'duolingo.com'] },
        other: { label: 'Other', icon: '🔗', risk: 0.5, domains: [] },
    },

    categorize(domain) {
        for (const [key, cat] of Object.entries(this.CATEGORIES)) {
            if (cat.domains.some(d => domain.endsWith(d) || domain === d)) {
                return { category: key, ...cat };
            }
        }
        return { category: 'other', ...this.CATEGORIES.other };
    },

    analyzeActivityLevel(signupDate) {
        if (!signupDate || signupDate === 'Unknown') return { level: 'unknown', score: 0.5, label: 'Unknown' };
        const months = this._monthsSince(signupDate);
        if (months > 60) return { level: 'dormant', score: 0.9, label: 'Dormant (5+ years)' };
        if (months > 36) return { level: 'inactive', score: 0.7, label: 'Inactive (3+ years)' };
        if (months > 12) return { level: 'stale', score: 0.4, label: 'Stale (1+ year)' };
        return { level: 'recent', score: 0.1, label: 'Recent' };
    },

    assessDataExposure(domain, category) {
        const cat = this.CATEGORIES[category] || this.CATEGORIES.other;
        const baseRisk = cat.risk;
        // Adjust by known data practices
        const heavyCollectors = ['facebook.com', 'instagram.com', 'linkedin.com', 'google.com', 'amazon.com'];
        const multiplier = heavyCollectors.some(d => domain.endsWith(d)) ? 1.3 : 1.0;
        return Math.min(baseRisk * multiplier, 1.0);
    },

    _monthsSince(dateStr) {
        try {
            const d = new Date(dateStr + '-01');
            const now = new Date();
            return (now.getFullYear() - d.getFullYear()) * 12 + (now.getMonth() - d.getMonth());
        } catch (e) { return 0; }
    }
};

// ─── RISK ENGINE ──────────────────────────────────────────────
const RiskEngine = {
    // Known breach databases (simulated lookup — in production, query HaveIBeenPwned API)
    KNOWN_BREACHES: {
        'linkedin.com': { year: 2021, records: '700M', severity: 'critical' },
        'facebook.com': { year: 2021, records: '533M', severity: 'critical' },
        'twitter.com': { year: 2023, records: '200M', severity: 'high' },
        'dropbox.com': { year: 2016, records: '68M', severity: 'high' },
        'adobe.com': { year: 2013, records: '153M', severity: 'high' },
        'canva.com': { year: 2019, records: '137M', severity: 'high' },
        'myspace.com': { year: 2016, records: '360M', severity: 'critical' },
        'yahoo.com': { year: 2017, records: '3B', severity: 'critical' },
    },

    PLATFORM_REPUTATION: {
        excellent: ['github.com', 'notion.so', 'figma.com', 'vercel.com', 'linear.app'],
        good: ['spotify.com', 'slack.com', 'trello.com', 'asana.com'],
        moderate: ['discord.com', 'reddit.com', 'medium.com'],
        poor: ['facebook.com', 'instagram.com', 'tiktok.com'],
    },

    calculateMultiFactorRisk(account) {
        const weights = {
            age: 0.15,
            category: 0.20,
            breachHistory: 0.25,
            dataExposure: 0.20,
            platformReputation: 0.10,
            confidence: 0.10,
        };

        const scores = {};

        // Age factor
        const activity = AccountAnalyzer.analyzeActivityLevel(account.signupDate);
        scores.age = activity.score;

        // Category factor
        const catInfo = AccountAnalyzer.categorize(account.domain);
        scores.category = catInfo.risk;

        // Breach history
        const breach = this.KNOWN_BREACHES[account.domain];
        scores.breachHistory = breach
            ? ({ critical: 1.0, high: 0.8, medium: 0.5, low: 0.2 }[breach.severity] || 0.5)
            : 0.1;

        // Data exposure
        scores.dataExposure = AccountAnalyzer.assessDataExposure(account.domain, catInfo.category);

        // Platform reputation
        scores.platformReputation = this._getReputationScore(account.domain);

        // Confidence from scan
        scores.confidence = account.confidence || 0.5;

        // Weighted sum
        let total = 0;
        for (const [key, weight] of Object.entries(weights)) {
            total += (scores[key] || 0) * weight;
        }

        return {
            totalScore: Math.round(total * 100) / 100,
            level: total >= 0.7 ? 'Critical' : total >= 0.5 ? 'High' : total >= 0.3 ? 'Medium' : 'Low',
            factors: scores,
            breach: breach || null,
            recommendation: this._getRecommendation(total, catInfo.category),
        };
    },

    _getReputationScore(domain) {
        for (const [tier, domains] of Object.entries(this.PLATFORM_REPUTATION)) {
            if (domains.some(d => domain.endsWith(d))) {
                return { excellent: 0.1, good: 0.3, moderate: 0.5, poor: 0.8 }[tier] || 0.5;
            }
        }
        return 0.5; // Unknown
    },

    _getRecommendation(score, category) {
        if (score >= 0.7) return 'Immediate deletion recommended. This account poses significant privacy risk.';
        if (score >= 0.5) return 'Deletion recommended. Review what data this service may hold.';
        if (score >= 0.3) return 'Consider deletion if no longer needed. Low-moderate risk.';
        return 'Low risk. Delete at your convenience or keep if actively used.';
    },
};

// ─── PATTERN DETECTOR ─────────────────────────────────────────
const PatternDetector = {
    // TF-IDF inspired keyword weights for signup detection
    KEYWORD_WEIGHTS: {
        'welcome': { weight: 0.35, context: 'subject' },
        'verify': { weight: 0.40, context: 'subject' },
        'confirm': { weight: 0.38, context: 'subject' },
        'activate': { weight: 0.42, context: 'subject' },
        'registration': { weight: 0.45, context: 'subject' },
        'get started': { weight: 0.30, context: 'subject' },
        'signed up': { weight: 0.50, context: 'body' },
        'account created': { weight: 0.48, context: 'subject' },
        'email confirmation': { weight: 0.45, context: 'subject' },
        'one more step': { weight: 0.35, context: 'subject' },
        'almost there': { weight: 0.32, context: 'subject' },
        'noreply': { weight: 0.20, context: 'sender' },
        'no-reply': { weight: 0.20, context: 'sender' },
        'accounts@': { weight: 0.25, context: 'sender' },
        'notifications@': { weight: 0.15, context: 'sender' },
    },

    // Bayesian prior probabilities for email classification
    PRIORS: {
        signup: 0.15,       // P(signup email) - base rate
        marketing: 0.40,    // P(marketing email)
        transactional: 0.25,
        personal: 0.20,
    },

    classifyEmail(from, subject, snippet) {
        const features = this._extractFeatures(from, subject, snippet);
        const scores = {
            signup: this.PRIORS.signup,
            marketing: this.PRIORS.marketing,
            transactional: this.PRIORS.transactional,
        };

        // Apply Bayesian-like updates based on features
        for (const feature of features) {
            const kw = this.KEYWORD_WEIGHTS[feature.term];
            if (kw) {
                scores.signup *= (1 + kw.weight * 2);
                scores.marketing *= (1 - kw.weight * 0.3);
            }
        }

        // Normalize
        const total = Object.values(scores).reduce((a, b) => a + b, 0);
        for (const key of Object.keys(scores)) {
            scores[key] = Math.round((scores[key] / total) * 100) / 100;
        }

        return {
            classification: Object.entries(scores).sort((a, b) => b[1] - a[1])[0][0],
            probabilities: scores,
            features: features,
            isSignup: scores.signup > 0.4,
            confidence: scores.signup,
        };
    },

    _extractFeatures(from, subject, snippet) {
        const features = [];
        const allText = `${from} ${subject} ${snippet}`.toLowerCase();

        for (const [term, config] of Object.entries(this.KEYWORD_WEIGHTS)) {
            if (allText.includes(term)) {
                features.push({ term, weight: config.weight, context: config.context });
            }
        }

        return features.sort((a, b) => b.weight - a.weight);
    },
};

// ─── DELETION ADVISOR ─────────────────────────────────────────
const DeletionAdvisor = {
    prioritize(accounts) {
        if (!accounts || !accounts.length) return [];

        return accounts.map(account => {
            const risk = RiskEngine.calculateMultiFactorRisk(account);
            const category = AccountAnalyzer.categorize(account.domain);
            const activity = AccountAnalyzer.analyzeActivityLevel(account.signupDate);

            // Priority score: higher = delete first
            let priority = risk.totalScore * 40;     // Risk is primary factor
            priority += activity.score * 25;          // Older = higher priority
            priority += (1 - (account.confidence || 0.5)) * 10; // Less confident = check
            priority += (category.risk || 0.5) * 25;  // Category risk

            return {
                ...account,
                aiRisk: risk,
                aiCategory: category,
                aiActivity: activity,
                aiPriority: Math.round(priority),
                aiDifficulty: this._estimateDifficulty(account.domain),
            };
        }).sort((a, b) => b.aiPriority - a.aiPriority);
    },

    _estimateDifficulty(domain) {
        // Known difficulty levels for deletion
        const easy = ['notion.so', 'figma.com', 'linear.app', 'vercel.com', 'netlify.com', 'github.com'];
        const hard = ['facebook.com', 'instagram.com', 'amazon.com', 'google.com', 'apple.com'];
        const moderate = ['spotify.com', 'dropbox.com', 'linkedin.com', 'twitter.com'];

        if (easy.some(d => domain.endsWith(d))) return { level: 'Easy', score: 0.2, note: 'Self-service deletion available' };
        if (hard.some(d => domain.endsWith(d))) return { level: 'Hard', score: 0.9, note: 'May require multiple steps & verification' };
        if (moderate.some(d => domain.endsWith(d))) return { level: 'Moderate', score: 0.5, note: 'Email request typically required' };
        return { level: 'Unknown', score: 0.5, note: 'Standard GDPR/CCPA request process' };
    },

    generatePlan(accounts) {
        const prioritized = this.prioritize(accounts);
        const phases = {
            immediate: [],  // Priority > 70
            soon: [],       // Priority 40-70
            later: [],      // Priority < 40
        };

        prioritized.forEach(acc => {
            if (acc.aiPriority > 70) phases.immediate.push(acc);
            else if (acc.aiPriority > 40) phases.soon.push(acc);
            else phases.later.push(acc);
        });

        return {
            phases,
            totalAccounts: accounts.length,
            estimatedTime: this._estimateTime(prioritized),
            summary: `${phases.immediate.length} accounts require immediate attention, ${phases.soon.length} should be addressed soon, ${phases.later.length} are low priority.`,
        };
    },

    _estimateTime(accounts) {
        const avgMinutes = accounts.reduce((sum, acc) => {
            const diff = acc.aiDifficulty?.score || 0.5;
            return sum + (diff * 10 + 5); // 5-15 minutes per account
        }, 0);
        return Math.ceil(avgMinutes);
    },
};

// ─── RESPONSE CLASSIFIER ──────────────────────────────────────
const ResponseClassifier = {
    RESPONSE_PATTERNS: {
        acknowledged: {
            keywords: ['received', 'processing', 'working on', 'will be deleted', 'request has been received', 'within 30 days', 'within one month'],
            label: 'Acknowledged',
            icon: '📬',
            action: 'Wait for completion confirmation. Follow up if no response within deadline.',
        },
        verification: {
            keywords: ['verify your identity', 'proof of identity', 'government id', 'identification', 'verify that you are', 'confirm your identity', 'additional verification'],
            label: 'Identity Verification Required',
            icon: '🔐',
            action: 'Provide requested identification to proceed with deletion.',
        },
        completed: {
            keywords: ['has been deleted', 'data has been removed', 'erasure complete', 'deletion confirmed', 'removed from our systems', 'no longer hold', 'request fulfilled'],
            label: 'Deletion Confirmed',
            icon: '✅',
            action: 'Deletion complete. No further action needed.',
        },
        refused: {
            keywords: ['unable to comply', 'cannot process', 'legitimate interest', 'legal obligation', 'exempt', 'not able to delete', 'refuse', 'denied'],
            label: 'Request Refused',
            icon: '⛔',
            action: 'Consider filing a complaint with your local data protection authority.',
        },
        partial: {
            keywords: ['partially deleted', 'some data', 'retained for', 'backup retention', 'except for', 'certain records'],
            label: 'Partial Deletion',
            icon: '⚠️',
            action: 'Review which data was retained and whether the retention is lawful.',
        },
    },

    classify(responseText) {
        if (!responseText) return { status: 'no_response', label: 'No Response', icon: '○', confidence: 0 };

        const text = responseText.toLowerCase();
        let bestMatch = null;
        let bestScore = 0;

        for (const [status, config] of Object.entries(this.RESPONSE_PATTERNS)) {
            const matches = config.keywords.filter(kw => text.includes(kw));
            const score = matches.length / config.keywords.length;

            if (score > bestScore) {
                bestScore = score;
                bestMatch = { status, ...config, confidence: Math.round(score * 100) / 100, matchedKeywords: matches };
            }
        }

        if (bestMatch && bestScore > 0) return bestMatch;
        return { status: 'unclear', label: 'Response Unclear', icon: '❓', confidence: 0, action: 'Manually review the response and classify accordingly.' };
    },
};

// ─── FOOTPRINT MAPPER ─────────────────────────────────────────
const FootprintMapper = {
    buildGraph(accounts) {
        if (!accounts || !accounts.length) return { nodes: [], edges: [], clusters: {} };

        const nodes = accounts.map(acc => {
            const category = AccountAnalyzer.categorize(acc.domain);
            return {
                id: acc.id,
                domain: acc.domain,
                company: acc.company,
                category: category.category,
                categoryLabel: category.label,
                icon: category.icon,
                risk: RiskEngine.calculateMultiFactorRisk(acc).totalScore,
            };
        });

        // Build edges: accounts that might share data (same category or known integrations)
        const edges = [];
        const INTEGRATIONS = [
            ['google.com', 'youtube.com'], ['facebook.com', 'instagram.com'],
            ['slack.com', 'notion.so'], ['github.com', 'vercel.com'],
            ['github.com', 'netlify.com'], ['shopify.com', 'mailchimp.com'],
            ['salesforce.com', 'hubspot.com'],
        ];

        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                // Same category connection
                if (nodes[i].category === nodes[j].category) {
                    edges.push({ source: nodes[i].id, target: nodes[j].id, type: 'category', weight: 0.3 });
                }
                // Known integration
                for (const [a, b] of INTEGRATIONS) {
                    if ((nodes[i].domain.endsWith(a) && nodes[j].domain.endsWith(b)) ||
                        (nodes[i].domain.endsWith(b) && nodes[j].domain.endsWith(a))) {
                        edges.push({ source: nodes[i].id, target: nodes[j].id, type: 'integration', weight: 0.8 });
                    }
                }
            }
        }

        // Cluster by category
        const clusters = {};
        nodes.forEach(n => {
            if (!clusters[n.category]) clusters[n.category] = { label: n.categoryLabel, icon: n.icon, accounts: [] };
            clusters[n.category].accounts.push(n);
        });

        return { nodes, edges, clusters };
    },

    generateInsights(accounts) {
        const graph = this.buildGraph(accounts);
        const insights = [];

        // High-risk cluster detection
        for (const [cat, cluster] of Object.entries(graph.clusters)) {
            const avgRisk = cluster.accounts.reduce((s, a) => s + a.risk, 0) / cluster.accounts.length;
            if (avgRisk > 0.6 && cluster.accounts.length > 1) {
                insights.push({
                    type: 'warning',
                    title: `High-risk ${cluster.label} cluster`,
                    message: `${cluster.accounts.length} ${cluster.label.toLowerCase()} accounts with average risk score ${Math.round(avgRisk * 100)}%. Consider prioritizing this category.`,
                    accounts: cluster.accounts.map(a => a.company),
                });
            }
        }

        // Data sharing risk
        const integrationEdges = graph.edges.filter(e => e.type === 'integration');
        if (integrationEdges.length > 0) {
            insights.push({
                type: 'info',
                title: 'Linked services detected',
                message: `${integrationEdges.length} known integration(s) found between your accounts. Deleting one may affect connected services.`,
            });
        }

        // Dormant accounts alert
        const dormant = accounts.filter(a => {
            const activity = AccountAnalyzer.analyzeActivityLevel(a.signupDate);
            return activity.level === 'dormant';
        });
        if (dormant.length > 0) {
            insights.push({
                type: 'alert',
                title: `${dormant.length} dormant account(s)`,
                message: `Accounts inactive for 5+ years. These are prime candidates for deletion as they increase your attack surface without providing value.`,
                accounts: dormant.map(a => a.company),
            });
        }

        return insights;
    },
};

// ─── AI ENGINE FACADE ─────────────────────────────────────────
const AIEngine = {
    analyzer: AccountAnalyzer,
    risk: RiskEngine,
    patterns: PatternDetector,
    advisor: DeletionAdvisor,
    classifier: ResponseClassifier,
    mapper: FootprintMapper,

    analyzeAccount(account) {
        return {
            category: AccountAnalyzer.categorize(account.domain),
            risk: RiskEngine.calculateMultiFactorRisk(account),
            activity: AccountAnalyzer.analyzeActivityLevel(account.signupDate),
            exposure: AccountAnalyzer.assessDataExposure(
                account.domain,
                AccountAnalyzer.categorize(account.domain).category
            ),
        };
    },

    analyzeAll(accounts) {
        const plan = DeletionAdvisor.generatePlan(accounts);
        const insights = FootprintMapper.generateInsights(accounts);
        const graph = FootprintMapper.buildGraph(accounts);

        return { plan, insights, graph };
    },

    classifyResponse(text) {
        return ResponseClassifier.classify(text);
    },
};
