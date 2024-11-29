// Copyrights C-EGG inc.
var tenhou = function(type, tehaiInput) {
    var u = function() {
        function b(a) {
            var b = a & 7
              , c = 0
              , d = 0;
            1 == b || 4 == b ? c = d = 1 : 2 == b && (c = d = 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 > b)
                return !1;
            c = d;
            d = 0;
            1 == b || 4 == b ? (c += 1,
            d += 1) : 2 == b && (c += 2,
            d += 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 > b)
                return !1;
            c = d;
            d = 0;
            1 == b || 4 == b ? (c += 1,
            d += 1) : 2 == b && (c += 2,
            d += 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 > b)
                return !1;
            c = d;
            d = 0;
            1 == b || 4 == b ? (c += 1,
            d += 1) : 2 == b && (c += 2,
            d += 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 > b)
                return !1;
            c = d;
            d = 0;
            1 == b || 4 == b ? (c += 1,
            d += 1) : 2 == b && (c += 2,
            d += 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 > b)
                return !1;
            c = d;
            d = 0;
            1 == b || 4 == b ? (c += 1,
            d += 1) : 2 == b && (c += 2,
            d += 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 > b)
                return !1;
            c = d;
            d = 0;
            1 == b || 4 == b ? (c += 1,
            d += 1) : 2 == b && (c += 2,
            d += 2);
            a >>= 3;
            b = (a & 7) - c;
            if (0 != b && 3 != b)
                return !1;
            b = (a >> 3 & 7) - d;
            return 0 == b || 3 == b
        }
        function a(a, d) {
            if (0 == a) {
                if (128 <= (d & 448) && b(d - 128) || 65536 <= (d & 229376) && b(d - 65536) || 33554432 <= (d & 117440512) && b(d - 33554432))
                    return !0
            } else if (1 == a) {
                if (16 <= (d & 56) && b(d - 16) || 8192 <= (d & 28672) && b(d - 8192) || 4194304 <= (d & 14680064) && b(d - 4194304))
                    return !0
            } else if (2 == a && (2 <= (d & 7) && b(d - 2) || 1024 <= (d & 3584) && b(d - 1024) || 524288 <= (d & 1835008) && b(d - 524288)))
                return !0;
            return !1
        }
        function g(a, b) {
            return a[b + 0] << 0 | a[b + 1] << 3 | a[b + 2] << 6 | a[b + 3] << 9 | a[b + 4] << 12 | a[b + 5] << 15 | a[b + 6] << 18 | a[b + 7] << 21 | a[b + 8] << 24
        }
        function d(c) {
            var d = 1 << c[27] | 1 << c[28] | 1 << c[29] | 1 << c[30] | 1 << c[31] | 1 << c[32] | 1 << c[33];
            if (16 <= d)
                return !1;
            if (2 == (d & 3) && 2 == c[0] * c[8] * c[9] * c[17] * c[18] * c[26] * c[27] * c[28] * c[29] * c[30] * c[31] * c[32] * c[33] || !(d & 10) && 7 == (2 == c[0]) + (2 == c[1]) + (2 == c[2]) + (2 == c[3]) + (2 == c[4]) + (2 == c[5]) + (2 == c[6]) + (2 == c[7]) + (2 == c[8]) + (2 == c[9]) + (2 == c[10]) + (2 == c[11]) + (2 == c[12]) + (2 == c[13]) + (2 == c[14]) + (2 == c[15]) + (2 == c[16]) + (2 == c[17]) + (2 == c[18]) + (2 == c[19]) + (2 == c[20]) + (2 == c[21]) + (2 == c[22]) + (2 == c[23]) + (2 == c[24]) + (2 == c[25]) + (2 == c[26]) + (2 == c[27]) + (2 == c[28]) + (2 == c[29]) + (2 == c[30]) + (2 == c[31]) + (2 == c[32]) + (2 == c[33]))
                return !0;
            if (d & 2)
                return !1;
            var r = c[0] + c[3] + c[6]
              , m = c[1] + c[4] + c[7]
              , n = c[9] + c[12] + c[15]
              , e = c[10] + c[13] + c[16]
              , q = c[18] + c[21] + c[24]
              , k = c[19] + c[22] + c[25]
              , p = (r + m + (c[2] + c[5] + c[8])) % 3;
            if (1 == p)
                return !1;
            var l = (n + e + (c[11] + c[14] + c[17])) % 3;
            if (1 == l)
                return !1;
            var t = (q + k + (c[20] + c[23] + c[26])) % 3;
            if (1 == t || 1 != (2 == p) + (2 == l) + (2 == t) + (2 == c[27]) + (2 == c[28]) + (2 == c[29]) + (2 == c[30]) + (2 == c[31]) + (2 == c[32]) + (2 == c[33]))
                return !1;
            r = (1 * r + 2 * m) % 3;
            m = g(c, 0);
            n = (1 * n + 2 * e) % 3;
            e = g(c, 9);
            q = (1 * q + 2 * k) % 3;
            c = g(c, 18);
            return d & 4 ? !(p | r | l | n | t | q) && b(m) && b(e) && b(c) : 2 == p ? !(l | n | t | q) && b(e) && b(c) && a(r, m) : 2 == l ? !(t | q | p | r) && b(c) && b(m) && a(n, e) : 2 == t ? !(p | r | l | n) && b(m) && b(e) && a(q, c) : !1
        }
        return function(a, b) {
            if (34 == b)
                return d(a)
        }
    }();
    var E = function() {
        function b(a) {
            e[a] -= 2;
            ++p
        }
        function a(a) {
            e[a] += 2;
            --p
        }
        function g(a) {
            --e[a];
            --e[a + 1];
            --e[a + 2];
            ++q
        }
        function d(a) {
            ++e[a];
            ++e[a + 1];
            ++e[a + 2];
            --q
        }
        function c(a) {
            --e[a];
            --e[a + 1];
            ++k
        }
        function f(a) {
            ++e[a];
            ++e[a + 1];
            --k
        }
        function r(a) {
            --e[a];
            --e[a + 2];
            ++k
        }
        function m(a) {
            ++e[a];
            ++e[a + 2];
            --k
        }
        var n = 0, e, q = 0, k = 0, p = 0, l = 0, t = 0, v = 0;
        return {
            g: 8,
            v: function() {
                var a = 8 - 2 * q - k - p
                  , b = q + k;
                p ? b += p - 1 : t && v && (t | v) == t && ++a;
                4 < b && (a += b - 4);
                -1 != a && a < l && (a = l);
                a < this.g && (this.g = a)
            },
            l: function(a, b) {
                e = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
                v = t = l = p = k = q = 0;
                this.g = 8;
                if (136 == b)
                    for (b = 0; 136 > b; ++b)
                        a[b] && ++e[b >> 2];
                else if (34 == b)
                    for (b = 0; 34 > b; ++b)
                        e[b] = a[b];
                else
                    for (--b; 0 <= b; --b)
                        ++e[a[b] >> 2]
            },
            j: function() {
                return e[0] + e[1] + e[2] + e[3] + e[4] + e[5] + e[6] + e[7] + e[8] + e[9] + e[10] + e[11] + e[12] + e[13] + e[14] + e[15] + e[16] + e[17] + e[18] + e[19] + e[20] + e[21] + e[22] + e[23] + e[24] + e[25] + e[26] + e[27] + e[28] + e[29] + e[30] + e[31] + e[32] + e[33]
            },
            o: function() {
                var a = (2 <= e[0]) + (2 <= e[8]) + (2 <= e[9]) + (2 <= e[17]) + (2 <= e[18]) + (2 <= e[26]) + (2 <= e[27]) + (2 <= e[28]) + (2 <= e[29]) + (2 <= e[30]) + (2 <= e[31]) + (2 <= e[32]) + (2 <= e[33])
                  , b = (0 != e[0]) + (0 != e[8]) + (0 != e[9]) + (0 != e[17]) + (0 != e[18]) + (0 != e[26]) + (0 != e[27]) + (0 != e[28]) + (0 != e[29]) + (0 != e[30]) + (0 != e[31]) + (0 != e[32]) + (0 != e[33])
                  , d = b + (0 != e[1]) + (0 != e[2]) + (0 != e[3]) + (0 != e[4]) + (0 != e[5]) + (0 != e[6]) + (0 != e[7]) + (0 != e[10]) + (0 != e[11]) + (0 != e[12]) + (0 != e[13]) + (0 != e[14]) + (0 != e[15]) + (0 != e[16]) + (0 != e[19]) + (0 != e[20]) + (0 != e[21]) + (0 != e[22]) + (0 != e[23]) + (0 != e[24]) + (0 != e[25])
                  , c = this.g
                  , d = 6 - (a + (2 <= e[1]) + (2 <= e[2]) + (2 <= e[3]) + (2 <= e[4]) + (2 <= e[5]) + (2 <= e[6]) + (2 <= e[7]) + (2 <= e[10]) + (2 <= e[11]) + (2 <= e[12]) + (2 <= e[13]) + (2 <= e[14]) + (2 <= e[15]) + (2 <= e[16]) + (2 <= e[19]) + (2 <= e[20]) + (2 <= e[21]) + (2 <= e[22]) + (2 <= e[23]) + (2 <= e[24]) + (2 <= e[25])) + (7 > d ? 7 - d : 0);
                d < c && (c = d);
                d = 13 - b - (a ? 1 : 0);
                d < c && (c = d);
                return c
            },
            m: function(a) {
                var b = 0, d = 0, c;
                for (c = 27; 34 > c; ++c)
                    switch (e[c]) {
                    case 4:
                        ++q;
                        b |= 1 << c - 27;
                        d |= 1 << c - 27;
                        ++l;
                        break;
                    case 3:
                        ++q;
                        break;
                    case 2:
                        ++p;
                        break;
                    case 1:
                        d |= 1 << c - 27
                    }
                l && 2 == a % 3 && --l;
                d && (v |= 134217728,
                (b | d) == b && (t |= 134217728))
            },
            w: function(a) {
                var b = 0, d = 0, c;
                for (c = 27; 34 > c; ++c)
                    switch (e[c]) {
                    case 4:
                        ++q;
                        b |= 1 << c - 18;
                        d |= 1 << c - 18;
                        ++l;
                        break;
                    case 3:
                        ++q;
                        break;
                    case 2:
                        ++p;
                        break;
                    case 1:
                        d |= 1 << c - 18
                    }
                for (c = 0; 9 > c; c += 8)
                    switch (e[c]) {
                    case 4:
                        ++q;
                        b |= 1 << c;
                        d |= 1 << c;
                        ++l;
                        break;
                    case 3:
                        ++q;
                        break;
                    case 2:
                        ++p;
                        break;
                    case 1:
                        d |= 1 << c
                    }
                l && 2 == a % 3 && --l;
                d && (v |= 134217728,
                (b | d) == b && (t |= 134217728))
            },
            s: function(a) {
                t |= (4 == e[0]) << 0 | (4 == e[1]) << 1 | (4 == e[2]) << 2 | (4 == e[3]) << 3 | (4 == e[4]) << 4 | (4 == e[5]) << 5 | (4 == e[6]) << 6 | (4 == e[7]) << 7 | (4 == e[8]) << 8 | (4 == e[9]) << 9 | (4 == e[10]) << 10 | (4 == e[11]) << 11 | (4 == e[12]) << 12 | (4 == e[13]) << 13 | (4 == e[14]) << 14 | (4 == e[15]) << 15 | (4 == e[16]) << 16 | (4 == e[17]) << 17 | (4 == e[18]) << 18 | (4 == e[19]) << 19 | (4 == e[20]) << 20 | (4 == e[21]) << 21 | (4 == e[22]) << 22 | (4 == e[23]) << 23 | (4 == e[24]) << 24 | (4 == e[25]) << 25 | (4 == e[26]) << 26;
                q += a;
                this.u(0)
            },
            u: function(h) {
                var k = arguments.callee;
                ++n;
                if (-1 != this.g) {
                    for (; 27 > h && !e[h]; ++h)
                        ;
                    if (27 == h)
                        return this.v();
                    var l = h;
                    8 < l && (l -= 9);
                    8 < l && (l -= 9);
                    switch (e[h]) {
                    case 4:
                        e[h] -= 3;
                        ++q;
                        7 > l && e[h + 2] && (e[h + 1] && (g(h),
                        k.call(this, h + 1),
                        d(h)),
                        r(h),
                        k.call(this, h + 1),
                        m(h));
                        8 > l && e[h + 1] && (c(h),
                        k.call(this, h + 1),
                        f(h));
                        var p = h;
                        --e[p];
                        v |= 1 << p;
                        k.call(this, h + 1);
                        p = h;
                        ++e[p];
                        v &= ~(1 << p);
                        e[h] += 3;
                        --q;
                        b(h);
                        7 > l && e[h + 2] && (e[h + 1] && (g(h),
                        k.call(this, h),
                        d(h)),
                        r(h),
                        k.call(this, h + 1),
                        m(h));
                        8 > l && e[h + 1] && (c(h),
                        k.call(this, h + 1),
                        f(h));
                        a(h);
                        break;
                    case 3:
                        e[h] -= 3;
                        ++q;
                        k.call(this, h + 1);
                        e[h] += 3;
                        --q;
                        b(h);
                        7 > l && e[h + 1] && e[h + 2] ? (g(h),
                        k.call(this, h + 1),
                        d(h)) : (7 > l && e[h + 2] && (r(h),
                        k.call(this, h + 1),
                        m(h)),
                        8 > l && e[h + 1] && (c(h),
                        k.call(this, h + 1),
                        f(h)));
                        a(h);
                        7 > l && 2 <= e[h + 2] && 2 <= e[h + 1] && (g(h),
                        g(h),
                        k.call(this, h),
                        d(h),
                        d(h));
                        break;
                    case 2:
                        b(h);
                        k.call(this, h + 1);
                        a(h);
                        7 > l && e[h + 2] && e[h + 1] && (g(h),
                        k.call(this, h),
                        d(h));
                        break;
                    case 1:
                        6 > l && 1 == e[h + 1] && e[h + 2] && 4 != e[h + 3] ? (g(h),
                        k.call(this, h + 2),
                        d(h)) : (p = h,
                        --e[p],
                        v |= 1 << p,
                        k.call(this, h + 1),
                        p = h,
                        ++e[p],
                        v &= ~(1 << p),
                        7 > l && e[h + 2] && (e[h + 1] && (g(h),
                        k.call(this, h + 1),
                        d(h)),
                        r(h),
                        k.call(this, h + 1),
                        m(h)),
                        8 > l && e[h + 1] && (c(h),
                        k.call(this, h + 1),
                        f(h)))
                    }
                }
            }
        }
    }();
    function F(b, a) {
        E.l(b, 34);
        var g = E.j();
        if (14 < g)
            return -2;
        !a && 13 <= g && (E.g = E.o(g));
        E.m(g);
        E.s(Math.floor((14 - g) / 3));
        return E.g
    }
    function G(b, a) {
        E.l(b, a);
        var g = E.j();
        if (!(14 < g)) {
            var d = [E.g, E.g];
            13 <= g && (d[0] = E.o(g));
            E.m(g);
            E.s(Math.floor((14 - g) / 3));
            d[1] = E.g;
            d[1] < d[0] && (d[0] = d[1]);
            return d
        }
    }
    ;function H(b) {
        var a = b >> 2;
        return (27 > a && 16 == b % 36 ? "0" : a % 9 + 1) + "mpsz".substr(a / 9, 1)
    }
    function J(b) {
        return b.replace(/\d(m|p|s|z)(\d\1)*/g, "$&:").replace(/(m|p|s|z)([^:])/g, "$2").replace(/:/g, "")
    }
    function aa(b) {
        b = b.replace(/(\d)m/g, "0$1").replace(/(\d)p/g, "1$1").replace(/(\d)s/g, "2$1").replace(/(\d)z/g, "3$1");
        var a, g = Array(136);
        for (a = 0; a < b.length; a += 2) {
            var d = b.substr(a, 2), c;
            d % 10 ? (c = 4 * (9 * Math.floor(d / 10) + (d % 10 - 1)),
            c = g[c + 3] ? g[c + 2] ? g[c + 1] ? c : c + 1 : c + 2 : c + 3) : c = 4 * (9 * d / 10 + 4) + 0;
            g[c] && document.write("err n=" + d + " k=" + c + "<br>");
            g[c] = 1
        }
        return g
    }
    ;function ba(b) {
        var a = parseInt(b.substr(0, 1));
        return (a ? a - 1 : 4) + 9 * "mpsz".indexOf(b.substr(1, 1))
    }
    function K(b) {
        var a, g = [];
        for (a = 0; 34 > a; ++a)
            4 <= b[a] || (b[a]++,
            u(b, 34) && g.push(a),
            b[a]--);
        return g
    }
    function ca(b) {
        var a, g = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        for (a = 0; 136 > a; ++a)
            b[a] && ++g[a >> 2];
        return g
    }
    function fa(tehai) {
        finalResult = {
            "success": 0,   //输入的手牌格式是否正确，正确为0，否则为-1，此时其余的数据为无效数据，应报错
            "xyanten": [0, 0],  // 向听数：index0为标准形向听数，index1为一般形向听数，数值为-1时表示和了
            "maisu": 14,    // 输入的手牌枚数
            "tehai": tehai, // 手牌序列：天凤手牌格式，如147m258p369s12345z
            "analys_type": 0, // 分析类型：0为标准形（含七对和国士）分析，1为一般形分析
            "machiList": {  // 打出牌后的进张或待牌，key为打出的牌; value为进张或待牌列表， 其中index0为待牌列表， index1为总枚数，如4m: [['1m', '7m'], 7]

            }
        }

        // 判断手牌长度是否>0，并检查字符的合法性，不通过则返回错误
        if (tehai.length < 1 || null == tehai.match(/^(\d+m|\d+p|\d+s|[1234567]+z)*$/))
        {
            finalResult["success"] = -1;
            return finalResult
        }

        function b(a, b) {
            var c, d = 0;
            for (c = 0; c < a.length; ++c)
                d += 4 - b[a[c]];
            return d
        }
        var a = ga, g = tehai;
        for (var c = "d" == a.substr(1, 1), a = a.substr(0, 1), g = g.replace(/(\d)(\d{0,8})(\d{0,8})(\d{0,8})(\d{0,8})(\d{0,8})(\d{0,8})(\d{8})(m|p|s|z)/g, "$1$9$2$9$3$9$4$9$5$9$6$9$7$9$8$9").replace(/(\d?)(\d?)(\d?)(\d?)(\d?)(\d?)(\d)(\d)(m|p|s|z)/g, "$1$9$2$9$3$9$4$9$5$9$6$9$7$9$8$9").replace(/(m|p|s|z)(m|p|s|z)+/g, "$1").replace(/^[^\d]/, ""), g = g.substr(0, 28), f = aa(g), r = -1; r = Math.floor(136 * Math.random()),
        f[r]; )
            ;
        var m = Math.floor(g.length / 2) % 3;
        // 判断手牌是否为3n + 2或3n + 2的形式，如果不是返回错误
        if ([1, 2].indexOf(m) == -1) {
            finalResult["success"] = -1;
            return finalResult
        }

        2 == m || c || (f[r] = 1,
        temp = H(r),
        g += temp,
        tehai += temp);
        var f = ca(f)
          , e = G(f, 34)
        // 向听数 ----------------------
        var xyanten = [e[0], e[1]];
        // 手牌枚数
        var maisu = Math.floor(g.length / 2)

        var q = "q" == a ? e[0] : e[1], k, p, l = Array(35);
        if (0 == q && 1 == m && c)
            k = 34,
            l[k] = K(f),
            l[k].length && (l[k] = {
                i: k,
                n: b(l[k], f),
                c: l[k]
            });
        else if (0 >= q)
            for (k = 0; 34 > k; ++k)
                f[k] && (f[k]--,
                l[k] = K(f),
                f[k]++,
                l[k].length && (l[k] = {
                    i: k,
                    n: b(l[k], f),
                    c: l[k]
                }));
        else if (2 == m || 1 == m && !c)
            for (k = 0; 34 > k; ++k) {
                if (f[k]) {
                    f[k]--;
                    l[k] = [];
                    for (p = 0; 34 > p; ++p)
                        k == p || 4 <= f[p] || (f[p]++,
                        F(f, "p" == a) == q - 1 && l[k].push(p),
                        f[p]--);
                    f[k]++;
                    l[k].length && (l[k] = {
                        i: k,
                        n: b(l[k], f),
                        c: l[k]
                    })
                }
            }
        else {
            k = 34;
            l[k] = [];
            for (p = 0; 34 > p; ++p)
                4 <= f[p] || (f[p]++,
                F(f, "p" == a) == q - 1 && l[k].push(p),
                f[p]--);
            l[k].length && (l[k] = {
                i: k,
                n: b(l[k], f),
                c: l[k]
            })
        }
        var t = [];
        for (k = 0; k < g.length; k += 2) {
            p = g.substr(k, 2);
            var v = ba(p)
              , h = J(g.replace(p, "").replace(/(\d)(m|p|s|z)/g, "$2$1$1,").replace(/00/g, "50").split(",").sort().join("").replace(/(m|p|s|z)\d(\d)/g, "$2$1"))
              , R = q + 1
              , I = l[v];
            I && I.n && (R = -1 == q ? 0 : q,
            void 0 == I.q && t.push(I),
            I.q = h);
            2 == m && (h += H(r));
        }
        l[34] && l[34].n && (l[34].q = J(g),
        t.push(l[34]));
        t.sort(function(a, b) {
            return b.n - a.n
        });
        for (k = 0; k < t.length; ++k) {
            v = t[k].i;
            var uchi = H(4 * v + 1);
            finalResult["machiList"][uchi] = [[], 0];
            l = t[k].c;
            c = t[k].q;
            for (p = 0; p < l.length; ++p)
                finalResult["machiList"][uchi][0].push(H(4 * l[p] + 1));
            finalResult["machiList"][uchi][1] = t[k].n;
        }

        finalResult["xyanten"] = xyanten;
        finalResult["maisu"] = maisu;
        finalResult["tehai"] = tehai;
        if (a == 'q') {
            finalResult["analys_type"] = 0
        }
        else {
            finalResult["analys_type"] = 1
        }
        return finalResult;
    }

    /*
    var O = tehaiInput
    , O = O.replace(/^([^=]+)=(.+)/, "$2")
    , ga = RegExp.$1;
    */
    var O = tehaiInput
    , ga = type
    return fa(O)
}

// tenhou(type, tehaiInput)的参数说明
// (q, <天凤标准格式手牌>)，q表示标准形分析（包含国士七对）
// (p, <天凤标准格式手牌>)，p表示一般形分析（不包含国士七对）
// 满足手牌数为3n + 2或3n + 1，长度超过14时会被截断

// tenhou(tehaiInput)的返回值说明
/*
finalResult = {
    "success": 0,   //输入的手牌格式是否正确，正确为0，否则为-1，此时其余的数据为无效数据，应报错
    "xyanten": [0, 0],  // 向听数：index0为标准形向听数，index1为一般形向听数，数值为-1时表示和了
    "maisu": 14,    // 输入的手牌枚数
    "tehai": tehai, // 手牌序列：天凤手牌格式，如147m258p369s12345z
    "analys_type": 0, // 分析类型：0为标准形（含七对和国士）分析，1为一般形分析
    "machiList": {  // 打出牌后的进张或待牌，key为打出的牌; value为进张或待牌列表， 其中index0为待牌列表， index1为总枚数，如4m: [['1m', '7m'], 7]
        4m: [['1m', '7m'], 7]
    }
}
*/

console.dir(tenhou("p", "112233556688m6s7s"), {depth: null})