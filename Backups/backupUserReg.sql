--
-- PostgreSQL database dump
--

-- Dumped from database version 12.18 (Ubuntu 12.18-0ubuntu0.20.04.1)
-- Dumped by pg_dump version 12.18 (Ubuntu 12.18-0ubuntu0.20.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: captcha; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.captcha (
    id integer NOT NULL,
    first_number integer NOT NULL,
    second_number integer NOT NULL,
    result integer NOT NULL,
    created timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.captcha OWNER TO postgres;

--
-- Name: captcha_attempts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.captcha_attempts (
    id integer NOT NULL,
    ip_address character varying(50),
    last_attempt_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    attempts integer DEFAULT 0
);


ALTER TABLE public.captcha_attempts OWNER TO postgres;

--
-- Name: captcha_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.captcha_attempts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.captcha_attempts_id_seq OWNER TO postgres;

--
-- Name: captcha_attempts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.captcha_attempts_id_seq OWNED BY public.captcha_attempts.id;


--
-- Name: captcha_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.captcha_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.captcha_id_seq OWNER TO postgres;

--
-- Name: captcha_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.captcha_id_seq OWNED BY public.captcha.id;


--
-- Name: tokens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tokens (
    id integer NOT NULL,
    login_token character varying(50) NOT NULL,
    expiration timestamp without time zone NOT NULL
);


ALTER TABLE public.tokens OWNER TO postgres;

--
-- Name: tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tokens_id_seq OWNER TO postgres;

--
-- Name: tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tokens_id_seq OWNED BY public.tokens.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    first_name character varying(50),
    last_name character varying(50),
    email character varying(50),
    password character varying(150),
    verification_status boolean DEFAULT false,
    verification_code character varying(50),
    token_id integer
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: captcha id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha ALTER COLUMN id SET DEFAULT nextval('public.captcha_id_seq'::regclass);


--
-- Name: captcha_attempts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha_attempts ALTER COLUMN id SET DEFAULT nextval('public.captcha_attempts_id_seq'::regclass);


--
-- Name: tokens id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tokens ALTER COLUMN id SET DEFAULT nextval('public.tokens_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: captcha; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.captcha (id, first_number, second_number, result, created) FROM stdin;
2	36	53	89	2024-03-28 10:45:55.853702
3	12	100	112	2024-03-28 10:48:09.557286
4	65	17	82	2024-03-28 10:49:55.261418
5	65	24	89	2024-03-28 10:51:25.336342
6	84	3	87	2024-03-28 10:51:44.59212
7	96	68	164	2024-03-28 11:46:43.938825
8	16	99	115	2024-03-28 11:49:33.647239
9	74	58	132	2024-03-28 11:56:00.69973
10	47	6	53	2024-03-28 11:59:26.286774
11	36	26	62	2024-03-28 12:03:00.90378
12	63	48	111	2024-03-28 12:09:16.914642
13	58	42	100	2024-03-28 12:10:55.071813
14	19	92	111	2024-03-28 12:11:55.964096
15	13	56	69	2024-03-28 12:19:55.508282
16	91	38	129	2024-03-28 12:25:37.597375
17	51	0	51	2024-03-28 12:27:17.734662
18	17	27	44	2024-03-28 12:28:16.755976
19	79	68	147	2024-03-28 12:29:24.703994
20	70	18	88	2024-03-28 12:32:30.662434
21	72	0	72	2024-03-28 12:33:17.643683
22	79	26	105	2024-03-28 12:35:32.321648
23	88	44	132	2024-03-28 12:37:01.426116
24	27	64	91	2024-03-28 12:38:37.449681
25	45	24	69	2024-03-28 12:39:25.506447
26	91	19	110	2024-03-28 12:40:17.805893
27	28	38	66	2024-03-28 12:40:50.063945
28	50	44	94	2024-03-28 12:41:16.491816
29	91	95	186	2024-03-28 12:44:20.617741
30	4	15	19	2024-03-28 12:44:20.631873
31	9	89	98	2024-03-28 12:45:04.474765
32	98	30	128	2024-03-28 12:48:08.439183
33	87	42	129	2024-03-28 12:49:53.022876
34	53	32	85	2024-03-28 12:50:32.858073
35	60	50	110	2024-03-28 12:50:46.266103
36	49	72	121	2024-03-28 12:59:03.546315
37	85	19	104	2024-03-28 12:59:56.555137
38	12	43	55	2024-03-28 14:02:29.114679
39	12	55	67	2024-03-28 14:03:05.189532
40	47	86	133	2024-03-28 14:03:29.522386
41	47	92	139	2024-03-28 14:03:52.335085
42	50	46	96	2024-03-28 14:04:18.506638
43	88	39	127	2024-03-28 14:05:58.138349
44	93	68	161	2024-03-28 14:06:49.646448
45	53	80	133	2024-03-28 14:07:18.653907
46	99	6	105	2024-03-28 14:08:04.237317
47	48	29	77	2024-03-28 14:08:21.883439
48	71	24	95	2024-03-28 14:11:36.700799
49	63	31	94	2024-03-28 14:12:43.766376
50	14	68	82	2024-03-28 14:14:29.683241
51	73	14	87	2024-03-28 14:18:01.846081
52	98	32	130	2024-03-28 14:18:29.722773
53	20	37	57	2024-03-28 14:18:59.602265
54	6	86	92	2024-03-28 14:19:13.834583
55	33	72	105	2024-03-28 14:27:17.447215
56	21	98	119	2024-03-28 14:28:08.660172
57	3	92	95	2024-03-28 14:29:28.964975
58	67	20	87	2024-03-28 14:29:51.491205
59	8	27	35	2024-03-28 14:30:20.298347
60	18	73	91	2024-03-28 14:30:32.583043
61	74	6	80	2024-03-28 14:30:48.158493
62	6	100	106	2024-03-28 17:32:20.320082
63	16	55	71	2024-03-29 10:40:28.086376
64	41	55	96	2024-03-29 10:54:58.083988
65	95	87	182	2024-03-29 10:55:24.659332
66	18	53	71	2024-03-29 11:21:19.983103
67	55	61	116	2024-03-29 11:21:39.078202
68	16	53	69	2024-03-29 11:23:12.351223
69	98	91	189	2024-03-29 11:37:37.378413
70	94	80	174	2024-03-29 11:39:44.842007
71	28	25	53	2024-03-29 11:42:02.791181
72	26	53	79	2024-03-29 11:45:09.196342
73	57	87	144	2024-03-29 11:48:01.517733
74	79	39	118	2024-03-29 11:49:05.610572
75	70	95	165	2024-03-29 11:49:26.167066
76	87	13	100	2024-03-29 11:50:48.249883
77	14	92	106	2024-03-29 11:50:48.40658
78	41	66	107	2024-03-29 11:52:48.710071
79	6	63	69	2024-03-29 11:53:21.670571
80	80	19	99	2024-03-29 11:53:55.423403
81	66	95	161	2024-03-29 11:58:25.721937
82	4	61	65	2024-03-29 11:59:20.287838
83	57	62	119	2024-03-29 12:01:11.901813
84	70	17	87	2024-03-29 12:01:36.410829
85	40	52	92	2024-03-29 12:02:34.350325
86	63	52	115	2024-03-29 14:29:17.714204
87	42	95	137	2024-03-29 14:29:45.896956
88	96	30	126	2024-03-29 14:30:03.930638
89	18	1	19	2024-03-29 14:30:07.694829
90	20	50	70	2024-03-29 14:30:40.9401
91	60	98	158	2024-03-29 14:32:18.978316
92	32	71	103	2024-03-29 14:33:04.618903
93	61	87	148	2024-03-29 14:34:21.851942
94	13	12	25	2024-03-29 14:35:43.325565
95	84	9	93	2024-03-29 14:35:56.346961
96	8	74	82	2024-03-29 14:36:25.076292
97	50	21	71	2024-03-29 14:36:34.498941
98	96	14	110	2024-03-29 14:37:51.707106
99	40	58	98	2024-03-29 14:38:40.14682
100	29	42	71	2024-03-29 14:39:29.696659
101	30	53	83	2024-03-29 14:47:11.919547
102	15	51	66	2024-03-29 14:48:04.875755
103	85	21	106	2024-03-29 14:48:59.822724
104	81	90	171	2024-03-29 14:49:34.857916
105	10	38	48	2024-03-29 14:55:18.922753
106	7	85	92	2024-03-29 14:55:56.342773
107	29	98	127	2024-03-29 14:56:05.790292
108	12	73	85	2024-03-29 14:57:19.357291
109	38	62	100	2024-03-29 14:57:46.904313
110	77	32	109	2024-03-29 14:57:55.244388
\.


--
-- Data for Name: captcha_attempts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.captcha_attempts (id, ip_address, last_attempt_time, attempts) FROM stdin;
\.


--
-- Data for Name: tokens; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tokens (id, login_token, expiration) FROM stdin;
2	9eb376ee981dd5a6c46b2eb20327e668f3ccd83ae3e38751	2024-03-26 15:05:08.657946
3	85986e236c07bdb9a90b515e93ace2c98514656c295c75eb	2024-03-26 15:08:23.961758
4	09ea69020664127619e16ebda290fc1624bdb0fea5b0b480	2024-03-26 15:13:51.048098
5	9e0534aa74e60b8953ef6417bd1b11faeb83a46fefdac2b4	2024-03-26 15:16:51.111597
6	43b9997bbc358b2db5d03e154f45f89fb6ca22dbc13ae0cf	2024-03-26 15:19:42.667059
7	c0bcfd1dcb1716a2b52021030c185e105d3b540863bb64f2	2024-03-26 16:38:31.567625
8	b815571db0387ee52c4c21ea28468948668e659850bfafff	2024-03-26 16:42:16.062271
9	8f3fd23c6cf5ded1386fd976f3d0aa448af70ac2e815771e	2024-03-26 16:43:52.775104
10	5aef0de67327a6f0ff9cc1a9f9135fdfc2a81c1de1ad8243	2024-03-26 16:45:42.296062
11	6b28bbf427292641837198298f07a843255d5dd9b1e330cb	2024-03-26 16:46:59.530294
12	3528a7dd5097616e5e7b25fbf86079083e2a0a142a4568ed	2024-03-26 17:04:43.276221
13	cd21f2730be52f28dc8d0feb70e065e7ab8939189905a08c	2024-03-26 17:05:46.719623
14	7415dfe3b59057580e936c4555bbee4af4ce7d633600df96	2024-03-26 17:07:41.305812
15	81916762745f1d702a60eb5d5ef166a2d0b179066007fd1b	2024-03-26 17:14:41.240913
16	b8c6a02100ebc9ea437970eabcf1f6c3d23c05c704af6260	2024-03-26 17:35:22.319811
17	ee88086b6dedacdf51bc32c25c24b169082abceabac435f8	2024-03-26 17:36:50.439187
18	b15bd9a0ff9c047ad63672ccfcbec7a2fc765c1162c754bb	2024-03-26 17:38:05.017574
19	f1cf61e8a187c0da4575a0da8ce6280b91bddf8499ec2ea0	2024-03-26 18:41:55.359447
20	543ee7fd82e08f4b9fb86a810e0442da74078fbb7d1c2567	2024-03-27 10:26:29.527329
21	01f9bdddd6f5d11030a06dcb257524fbd3b43db4546835cd	2024-03-27 10:51:38.728523
22	84067c8b54ec7d215a06d587ab6b3b078449b1c78f5a5416	2024-03-27 10:58:27.605074
23	8aa80f52ffcda997d82dbef81db27c9ddd1df6012e91f92a	2024-03-27 11:19:20.48801
24	db5896da1845f26aa4a8ae776ee04c1fda6c81e40381f068	2024-03-27 11:19:50.094119
25	26a79bf21c4980796b3d8e1fcbd8a5ac832cc00dde28599e	2024-03-27 11:22:09.472532
26	1e79dbd78b1b3c4bdfd67732ed6ae9c5fc7c0d0ac40033b1	2024-03-27 11:25:58.537364
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, first_name, last_name, email, password, verification_status, verification_code, token_id) FROM stdin;
89	Recover 	Password	wpw90538@zbock.com	$2b$12$7xkV9cseq4Tulig3AG3m6uEbsc.anxgYe0ZkaUael8L7KYFdRhmri	t	546fb8d4024373177b416754843cc46d9bd0834ee8d3516e	\N
1	Ameto we	Petrov	galin@gmail.com	123456789	t	zxcvbnmasdfghjklqwertyuiop	\N
2	Ameto we	VAlentivo	migo@gmail.com	123456789	f	e982016c5dda525fc1646f0641aac5f319ffb9715fa95edd	\N
3	Ameto we	Luciano	twiqqxocikorppckkn@cazlp.com	123456789	f	17a853499c39c624dc67a1d836e264188f05af3509a30e49	\N
4	Ameto we	Mishev	grc16892@nezid.com	123456789	f	482838c88498e18e42dbfde3efe4b8c65c825fa65c901e0c	\N
5	Ameto we	Nikolob	ffw87722@nezid.com	123456789	f	8ebd4673e2d94b8ea7c9f375d655d767fc2d739c18b8f9a9	\N
6	Ameto we	Georgieva	opd82235@omeie.com	123456789	f	e480bd6342b396ecbe95254f21fef42926376fe7d4afb033	\N
7	Ameto we	Vazzzka	euc58884@nezid.com	123456789	f	dcefa1a6430b99e7e946dfb1aa874194589a7d5acbb27cab	\N
8	Ameto we	Zahariev	jlb51017@zbock.com	123456789	f	92a197376145353b2a6912f374a789c22223f4521f9f0ffd	\N
9	Ameto we	Na Vanko	ltx98173@nezid.com	123456789	f	2ead03b564de9e8739e7b6af2d3af1f46de70ac997f91f05	\N
10	Ameto we	LIdulska	mug50504@zslsz.com	123456789	f	35345f19a0ff960952fb673a9ca827015db7744f49f5bc63	\N
11	Ameto we	Mishenska	oza74432@zbock.com	123456789	f	5fa08325d8e9029c394b2e25f90075c19624a7a6f1f2bfa8	\N
12	Ameto we	Pispis	ndj73134@nezid.com	123456789	f	2c6daeaed7e0e2fbce0b700c94bd21b882283ee5d7cf5ac3	\N
13	Ameto we	Kaji	kgc40946@zbock.com	123456789	f	b7296b274093403b119ec51c370e05f5cfb5ff97eb112675	\N
14	Ameto we	Sakiliinika	dyo21897@zslsz.com	123456789	f	128306c60c90af58449cabf9289e07884acd1bb8b48a7a06	\N
15	Ameto we	Kata	mpr30715@zbock.com	123456789	f	73bdfabadd46facd74bbcd9d92f87c17827ff2ef1825292e	\N
16	Ameto we	dfdfd	qiq45941@omeie.com	123456789	f	6da0770f4e7b6fb64a5bb55ed511c54fc3a1dcfcf4672756	\N
17	Ameto we	aaaaaaaa	aom55035@zslsz.com	123456789	f	69fefb78993423731c6df6548dd5f16113228bf431535b95	\N
18	Ameto we	vsdfvsd	hab73607@zslsz.com	123456789	f	cb5c700c14b62ec3ae4aae204418409b7e6248ef7f16f34e	\N
19	Ameto we	aaaaaa	nxz88115@zslsz.com	123456789	f	4ab523684e5ab3254f577d90e58c1dfb8f8d803b05e548f8	\N
20	Ameto we	aaaa	gsr53314@zbock.com	123456789	f	63c33846b7c818c0d705779721648fc6ccf85d21bb37b1ab	\N
21	Ameto we	qqqqqq	kyk88025@nezid.com	123456789	f	119667d0f7a65c06a3805221e8b549b44ab8e93bb6867fdc	\N
22	Ameto we	tytytytyty	efp73234@zslsz.com	123456789	t	73ef8dee4a68a4bb7c5527cb097c80027b0e9c9e5519402c	\N
97	Pesssssssssha	Pesssssssssha	xby21275@fosiq.com	$2b$12$Cb/7D7CmxdHpKOt8Spc8g.vmnsNvbxHV4zVNNiDL/doAdBJutPtw2	f	b52225054226b94cc047a70e57749ebad17c77b8ca4f3b47	6
48	Test	User	testusee@example.com	hashed_password	f	61aaf749f69a2ed8a1518e53196ca7c53bb73188d58b2410	\N
25	Ameto we	Ivanov	oed47454@zbock.com	$2b$12$AmLbDhqpgytNFAfo2Xn8ou2yCqCEqQrB/WRVm7JC4fHqvm6D5dnIe	f	15487487caf4e66f7f33c1b37d02585055c4b476d27d8869	\N
24	Didi	Teta	ewq42133@nezid.com	12345678	t	cd7be616803c62a94571ae336476eecb63c9cee828ac332c	\N
71	NA BABA TI FURCHILOTO	SETTTINGS	TAREZA@GMAIL.COM	$2b$12$YHfGP/AtvqLEfIr2dFa30O0KNtIuEztSLwqisNXGof1nBsVNLdqHW	t	db8f09ef992a76bf112462562321174287c2c055d472666e	\N
26	Pechkata	Na baba ti 	lsi72440@nezid.com	$2b$12$Rxh60uY9RuzvAzZVJzGRQuz2pWTukShishhGQP1R/.lKvaUywAP1W	f	90d87f744191c61a649baf9d8b7ba2bd2ac8add3d0ebfaf5	\N
27	Galin	Petrov	galincho112@gmail.com	$2b$12$aYgbsufOz4Kge1UP4SDBIOh/SIjJ9nv9titu.WUvq2G0MNoEgHrZ.	f	5f29a4d70a0334c729be9f8eee5c10910c87e65c2a37ed48	\N
75	Test	User	alooo@example.com	$2b$12$LTo1b1LEl.mp.97p8/4RdeUgivQmIwUOv0YKD0ab3rgGj59SlyWQm	t	5bba564cb2aaf2fe09d713bc98a75335047cd2072790c353	\N
30	Test	User	testuser@example.com	hashed_password	f	187732bd796328411f2fe15b54fdbeb0705e74aeed60dd81	\N
94	dpj55974@omeie.com	dpj55974@omeie.com	dpj55974@omeie.com	$2b$12$2VOq4VM7lK9MhwgSFXZgLOHo3zZRMxT8ifJ47fmNR.NgNdu2G.hQu	t	08cd67cb7570068a0b6ca623562befce0a8a8299eda2c058	\N
90	VERIFICATION	STATUS	kmj11855@nezid.com	$2b$12$eZpLc095b/Fg9PJx3dpm6.soxYuXnlZ6OyFmn3ePpshN8JUmvijgK	t	ac91a7bf73c9d3dc1e7bd94a7d5f1d3507cab05370eefeb0	\N
33	Test	User	testuse@example.com	hashed_password	f	09c79ca1314aa9a62a75f15ad1202db3b6bf4c5779f2d156	\N
96	Mishiii	Metanova	bly58097@vogco.com	$2b$12$n6kZicD6SrMGFWkR/mKnD.Y6NNzeF4E6pEJnsAr.xsj9skcYT263u	f	f0a3903d8f8bd444a87459d22731cc8287e2b45dc99903bd	\N
98	sadasdsa	dadasdas	rnb76293@romog.com	$2b$12$4xUvuY6U1Z2kkhLteJNn4u3OB.if4doJnklxsgZpMDq2pEG9g9aJy	f	68ca1af64eb0a38837b29a5f9f5ab36ff7817a9de03c94c6	\N
23	Ameto we	Barabata	ocb58375@zslsz.com	$2b$12$EM1jtkFATzDBzJwJosgu9.VZZOJmnltlnzp1WlyGd56VKvknxYxpW	t	ccb3e4ed0c726ca2b96939aad959226bd882e8b9340e1baa	\N
102	Angela 	Kostadinovska 	a.kostadinovska@test.com	$2b$12$RrPfwubzh9xYhWQPl37fXOjC3vDbHWZg/tjMZyUgDEaEXX7qg99pu	f	822f05f6c29fc534a4f29f9243c685038c3cf3f99ae814fe	\N
53	Test	User	testuseer@example.com	hashed_password	f	5fc12f11004669d97503006b9b685e7535269cb25deb97cc	\N
56	MIEEEEEE	MIEEEEEE	xik10812@zbock.com	$2b$12$oASQVE.rjkekVGy/L6.AZ.TKPzLSEzsiphUELfc2MrDLKLxPdwgNK	t	3015cf57ec651c847431d3e97de306c4d0e03759a42d76ec	\N
59	Test	User	alooooooo@example.com	hashed_password	t	000000000000000000000000000000000000000000000000	23
58	Test	User	testuseerqq@example.com	hashed_password	f	1abe612ef88274161ca630f7af502a61e38428be777b8d08	\N
103	Angela 	Kostadinovska 	a.kostadinovska16@gmail.com	$2b$12$ETtEA3Z8W.jO9zKzSYKgZ.2IKnxAOoQFNEiSC9GbVXd8RhHMm4ACG	f	967f1cf859bd6df5c4753704c815258f748564cee0515333	\N
57	Shinka	Kotruleva	ndu41706@zslsz.com	$2b$12$n07/pTtYauh80z/tvf7knuKUVFT5fRmr5/qkWwHt71SzYAs.dtjwS	t	6378bd56663550da755f51e148df6ef9e13bbed5a970f7ff	\N
99	Аngela 	Kostadinovska 	angela@telebid-intern.com	$2b$12$.65mcmAsn/ijicAf6lpjdeSyx7xe6T5hg5GtaWIoWvhY5jLoBalt6	t	accd6b46d3f2aeb673fd9909292a52f97f03ce7e8c93c994	\N
82	Zenkat	Alab	usi60546@zbock.com	$2b$12$Etttgv6Ul6J0T3qZnnJ0le/XQuzVPBy8F7S1LT7cZBYunORPTk6e2	t	7d861239df7c1d097f58168a17f67536c943d69cb66e359b	\N
72	fsdfsdfsdfsd	fsgdgstrhtrh	gem29205@nezid.com	$2b$12$uKGtY5scdvuyo46svSerxeI2sPh9F.JPh4XS1zWnkxXpLUkjyk9mO	f	423c3f38f30be29c842330f33ec1a1d7360c600267efcfdb	\N
133	sdsdsdsdsd	ssdsdsdsds	phk20418@fosiq.com	$2b$12$j.SVCZMx4SoppkEWo7jKYepUUBe1A1HF5P8//c7A5Jh7mrT81ZUvu	f	cda4be193833a45f7856109de952e7826b57aa8f9feb1f78	\N
134	Captcha	Testing	wzs50325@fosiq.com	$2b$12$QUCCH0c.B9nHAx2Wi8eMEeYQZkCCgSdHJe0aDB7Jvl4bKZM3I/pbm	f	bd7e21ab43a0ff17ba0d746603ee0a518d4c5345ea0c4bf1	\N
112	Angela 	Kostadinovska 	angela@angela.com	$2b$12$2mx1Zm17boFM1hF1Buk1D.ac5RAZjNge/Qc.ImRwMllwdy49Nu5A2	f	7cb3b8f3d09ecb94ee0c755d03d8775441cacf6369c363d4	\N
135	eee	eeee	eeeee@ee.com	$2b$12$r24jcH/VC145TmitwkNuUOdMsDY4C4v9otZpOQTfiXCY/dxDBE2s2	f	29d6bfb2ea3f3a2d8b3d91cbb6ec6657393f11a368af5cf7	\N
136	yeee	yeeeee	yee@yee.com	$2b$12$nOUTpUuxdOhuPQdUI10yjerPf/Io1a4WawlNck2iVP7g2Q9WBhuqa	f	7d14e3afad6f1374884719151228c6cd59790503dc21570a	\N
137	sdfdsfsdfsd	dfdsfsdf	iaz34989@fosiq.com	$2b$12$mgn8/RRAOMqq.fve3W7Q/u1KgmDFCtI9LmJ8Dno5fKKd9.nvCkSt.	f	567026a09e5d908f172149e23408b16f2d038814d1a6b37b	\N
95	Pesho	Ivanov	galin+2@telebid-intern.com	$2b$12$q3HwFXuNsdsBWfa83JLhHOnmA1rUWuMe0cxWUFgZTtB0qi3U3jaNK	t	3e01ba3c550405074a40eeb5580f1b5686380d9b05aaea44	\N
117	Milena 	Milena 	ak@ak.com	$2b$12$JWoOIajSdZofCWlDl/RyX.Y.JjGRMDAul5H3CAs7KfsC/.z0yzfxC	f	19010a4dd00ae2ab4d861044c5d1b26014faffb846a43c1d	\N
123	Betka 	Letka	ani@aa.com	$2b$12$MkczZkKl2Kw1ejKwoY1QhOnRXk1ysJkDjq6bWkeoBfckgKxPZ3UkS	f	7743c1d333d97e5ce4bd9f088afce1a5fbfa73edd45a9a51	\N
127	angie	ani	ani@an.com	$2b$12$U.WZhVH9sAvVUQV6nODBhuLTw8p.r5vNRhNhEJmsndvqm/n.Kl7H.	f	b4bb2005f443eaf295906e95561cb2baee8af188ebdac4cb	\N
111	Angela 	Kostadinovska 	ani@ani.com	$2b$12$GUXohgmx9UOTwI6KbCSYW.1rekYb7rLZL3UNon1XDmf9mkYTRVHse	f	eefb102640d9548406fbe32b7a4340704f19174b865c42c0	\N
129	555	555	em@am.com	$2b$12$1p3QLKRNn09X06z0GzQuJ.D70F/Vn7qTxgX2zxyJ428LBFlYIKZH.	f	328773337a6d9262d5ecad61c3a64138f8f26d9baf799a5c	\N
138	Miceff	Peshkata	hvw91259@vogco.com	$2b$12$xMr6ioQb4dJJoXpGKabmLOH/0jrU8jhMX7U18J0CCljsth23brnY2	t	af6174dcaaa283a8636184d3db4dfdfb130aafff56b68225	\N
\.


--
-- Name: captcha_attempts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.captcha_attempts_id_seq', 13, true);


--
-- Name: captcha_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.captcha_id_seq', 110, true);


--
-- Name: tokens_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tokens_id_seq', 27, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 138, true);


--
-- Name: captcha_attempts captcha_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha_attempts
    ADD CONSTRAINT captcha_attempts_pkey PRIMARY KEY (id);


--
-- Name: captcha captcha_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.captcha
    ADD CONSTRAINT captcha_pkey PRIMARY KEY (id);


--
-- Name: tokens tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tokens
    ADD CONSTRAINT tokens_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_token_id_fkey FOREIGN KEY (token_id) REFERENCES public.tokens(id);


--
-- Name: TABLE captcha; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.captcha TO myuser;


--
-- Name: TABLE captcha_attempts; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.captcha_attempts TO myuser;


--
-- Name: SEQUENCE captcha_attempts_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.captcha_attempts_id_seq TO myuser;


--
-- Name: SEQUENCE captcha_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.captcha_id_seq TO myuser;


--
-- Name: TABLE tokens; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.tokens TO myuser;


--
-- Name: SEQUENCE tokens_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.tokens_id_seq TO myuser;


--
-- Name: TABLE users; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.users TO myuser;


--
-- Name: SEQUENCE users_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.users_id_seq TO myuser;


--
-- PostgreSQL database dump complete
--

