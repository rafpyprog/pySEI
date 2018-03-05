import re
from bs4 import BeautifulSoup
from concurrent.futures import wait, as_completed, Future
from requests_futures.sessions import FuturesSession
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


URL_SEI = 'https://seimp.planejamento.gov.br/sei/'


class PageElement():
    url = URL_SEI
    def __init__(self, session, html):
        self.session = session
        self.soup = self.get_soup(html)

    def get_soup(self, html):
        return BeautifulSoup(html, 'lxml')


class ProcessoSei(PageElement):
    def __init__(self, session, html):
        super().__init__(session, html)
        self._arvore = None
        self._acoes = None
        self._documentos = {}

    @property
    def metadata(self):
        metadata = {}
        url = [i for i in self.acoes if 'consultar' in i][0]
        html = self.session.get(url, verify=False, timeout=60).text
        soup = self.get_soup(html)

        sel_assuntos = soup.find('select', {'id': 'selAssuntos'})
        assuntos = [i.text for i in sel_assuntos.find_all('option')]
        metadata['assuntos'] = assuntos

        sel_interessado = soup.find('select', {'id': 'selInteressadosProcedimento'})
        interessados = [i.text for i in sel_interessado.find_all('option')]
        metadata['interessados'] = interessados

        especificacao = soup.find('input', {'id': 'txtDescricao'})['value']
        metadata['especificacao'] = especificacao

        select_tipo = soup.find('select', {'id': 'selTipoProcedimento'})
        tipo = select_tipo.find('option', {'selected': 'selected'}).text
        metadata['tipo'] = tipo

        protocolo = soup.find('input', {'id': 'txtProtocoloExibir'})['value']
        metadata['protocolo'] = protocolo

        dt_autuacao = soup.find('input', {'id': 'txtDtaGeracaoExibir'})['value']
        metadata['data_autuacao'] = dt_autuacao

        metadata['documentos'] = self.documentos
        return metadata

    @property
    def arvore(self):
        if self._arvore is None:
            url = URL_SEI + self.soup.find('iframe', {'id': 'ifrArvore'})['src']
            r = self.session.get(url, verify=False, timeout=60)
            self._arvore = r.text
        return self._arvore

    @property
    def acoes(self):
        if self._acoes is None:
            HTML = self.arvore
            acoes = re.search('(?<=Nos\[0\].acoes = \').*', HTML).group()
            self._acoes = [URL_SEI + i for
                           i in re.findall('(?<=href=").*?(?="\stabindex)', acoes)]
        return self._acoes

    @property
    def documentos(self):
        if self._documentos == {}:
            HTML = self.arvore

            pattern_urls = ('(?<=Nos\[[0-999]\].src\s=\s\').*(?=\';)')
            urls_arvore = re.findall(pattern_urls, HTML)[1:]

            pattern = '(?<=Nos\[[0-999]\] = new infraArvoreNo\().*(?=\))'
            nos_arvore = re.findall(pattern, HTML)[1:]

            for i in ['",'.join(i) for i in zip(nos_arvore, urls_arvore)]:
                doc = Documento(self.session, i)
                self._documentos[doc.number] = doc
        return self._documentos

    def download_pdf(self, filename=None):
        if filename is None:
            filename = 'download_sei.pdf'
        self._download(filetype='pdf', filename=filename)

    def download_zip(self, filename=None):
        if filename is None:
            filename = 'download_sei.zip'
        self._download(filetype='zip', filename=filename)

    def _download(self, filetype, filename='download_sei.pdf'):
        url = [i for i in self.acoes if filetype in i][0]
        r = self.session.get(url, verify=False, timeout=60)
        soup = self.get_soup(r.content)
        url_gera_pdf = URL_SEI + soup.find('form')['action']
        # params para o post
        params = {i['id']: i['value'] for
                  i in soup.find_all('input')[:-1]
                  if i.get('type', None) == 'hidden'}
        params['hdnFlagGerar'] = 1

        for n, item in enumerate(params['hdnInfraItens'].split(',')):
            params['chkInfraItem{}'.format(n)] = item
        r = self.session.post(url_gera_pdf, verify=False, data=params, timeout=60)
        url_pdf = re.search('(?<=window.open\(\').*(?=\'\))', r.text).group()
        r = self.session.get(URL_SEI + url_pdf, verify=False, timeout=120)
        DOWNLOAD_CONTENT = r.content

        if r.headers.get('Content-Disposition', None) is not None:
            filename = r.headers.get('Content-Disposition').split('"')[-2]

        with open(filename, 'wb') as f:
            f.write(DOWNLOAD_CONTENT)


class ResultadoPesquisa(PageElement):
    def __init__(self, session, html):
        super().__init__(session, html)


class Documento():
    def __init__(self, session, attributes: str):
        self.session = session
        self.attributes = attributes
        self.parse_attributes(self.attributes)

    def parse_attributes(self, attributes):
        attrs = attributes.replace('",', '|').replace('"', '').split('|')
        self.url = URL_SEI + attrs[-1]
        self.name = attrs[5]
        number_pattern = '(?<=\s)[0-9]*$|(?<=\()[0-9]{1,8}(?!\))'
        self.number = attrs[5].split(' ')[-1].replace('(', '').replace(')', '')

    @property
    def filename(self):
        r = self.session.head(self.url)
        filename = r.headers.get('Content-Disposition', None)
        if filename:
            filename = re.search('(?<=filename=").*(?=")', filename).group()
        return filename

    @property
    def contents(self):
        r = self.session.get(self.url)
        return r.content

    def to_file(self, filename=''):
        if filename != '':
            outfile = filename
        else:
            outfile = self.filename or self.name

        with open(outfile, 'wb') as f:
            f.write(self.contents)


    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self.__class__) + self.name


class SEI():
    url = URL_SEI
    def __init__(self):
        self.session = requests.Session()
        self._form_url = None

    def login(self, nu_cpf, password):
        self.nu_cpf = nu_cpf
        self.password = password

        if self.is_online is False:
            raise SystemError('SEI offline.')

        # 1 - Página inicial
        r = self.session.get(self.url, verify=False, allow_redirects=False)
        url_login_php = r.headers['Location']

        # 2 - Captura o hndCaptcha'
        r = self.session.get(url_login_php)
        soup = BeautifulSoup(r.text, 'html.parser')
        hdn_captcha = soup.find('input', {'id': 'hdnCaptcha'})['value']

        #3 - Envia o form de Login'
        data = {"txtUsuario": self.nu_cpf,
                "pwdSenha": self.password,
                "selOrgao": "0",
                "sbmLogin": "Acessar",
                "hdnCaptcha": hdn_captcha}

        r = self.session.post(url_login_php, data=data, verify=False)

        try:
            soup = BeautifulSoup(r.content, 'html.parser')
            self.user = soup.find('a', {'id': 'lnkUsuarioSistema'})['title']
        except:
            print('Erro no login')
            return False

        self.html = r.content
        return True

    @property
    def is_online(self):
        r = requests.get(self.url, verify=False, allow_redirects=False)

    def acessa_tela_pesquisa(self):
        soup = BeautifulSoup(self.html, 'lxml')
        menu = soup.find('ul', {'id': 'main-menu'}).find_all('a')[3]
        url_pesquisa = self.url + menu['href']
        r = self.session.get(url_pesquisa, verify=False)
        self.html = r.text

    @property
    def form_URL(self):
        if self._form_url is None:
            self._form_url = self.get_form_URL()
        return self._form_url

    def get_form_URL(self):
        self.acessa_tela_pesquisa()
        soup = BeautifulSoup(self.html, 'lxml')
        url_pesquisa = soup.find('form', {'id': 'frmPesquisaProtocolo'})['action']
        return self.url + url_pesquisa

    def pesquisa(self, query='', nu_sei='', doc_gerados=True,
                 doc_recebidos=True, com_tramitacao=False):
        data = {
            'q': query,
            'sbmPesquisar':'Pesquisar',
            'txtUnidade': '',
            'hdnIdUnidade': '',
            'txtAssunto': '',
            'hdnIdAssunto': '',
            'txtAssinante': '',
            'hdnIdAssinante': '',
            'txtContato': '',
            'hdnIdContato': '',
            'chkSinInteressado': 'S',
            'chkSinRemetente': 'S',
            'chkSinDestinatario': 'S',
            'txtDescricaoPesquisa': '',
            'txtObservacaoPesquisa': '',
            'txtProtocoloPesquisa': nu_sei,
            'selTipoProcedimentoPesquisa': '',
            'selSeriePesquisa': '',
            'txtNumeroDocumentoPesquisa': '',
            'txtDataInicio': '',
            'txtDataFim': '',
            'txtUsuarioGerador1': '',
            'hdnIdUsuarioGerador1': '',
            'txtUsuarioGerador2': '',
            'hdnIdUsuarioGerador2': '',
            'txtUsuarioGerador3': '',
            'hdnIdUsuarioGerador3': '',
            'hdnInicio': '0'
            }

        if doc_gerados:
            data['chkSinDocumentosGerados'] = 'S'
        if doc_recebidos:
            data['chkSinDocumentosRecebidos'] = 'S'
        if com_tramitacao:
            data['chkSinProcessosTramitacao'] = 'S'


        r = self.session.post(self.form_URL, data=data, allow_redirects=False)
        processo_SEI = r.headers.get('Location', None)
        if processo_SEI:
            url_dados_processo = self.url + processo_SEI
            r = self.session.get(url_dados_processo)
            return ProcessoSei(self.session, r.text)
        else:
            return ResultadoPesquisa(self.session, r.text)
