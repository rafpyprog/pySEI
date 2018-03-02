import re
from bs4 import BeautifulSoup
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
        self.parse_arvore()

    @property
    def metadata(self):
        metadata = {}
        url = [i for i in procSei.acoes if 'consultar' in i][0]
        html = self.session.get(url).text
        soup = procSei.get_soup(html)

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

    def parse_arvore(self):
        url = self.url + self.soup.find('iframe', {'id': 'ifrArvore'})['src']
        r = self.session.get(url)
        html = r.text
        pattern = '(?<=Nos\[[0-999]\] = new infraArvoreNo\().*(?=\))'
        nos = re.findall(pattern, html)
        nos_arvore = nos[1:]

        acoes = re.search('(?<=Nos\[0\].acoes = \').*', html).group()
        self.acoes = [URL_SEI + i for
                      i in re.findall('(?<=href=").*?(?="\stabindex)',acoes)]

        pattern_urls = ('(?<=Nos\[[0-999]\].src\s=\s\').*(?=\';)')
        urls_arvore = re.findall(pattern_urls, html)[1:]
        self._documentos = ['",'.join(i) for i in zip(nos_arvore, urls_arvore)]

    def download_pdf(self, filename=None):
        if filename is None:
            filename = 'download_sei.pdf'
        self._download(filetype='pdf', filename=filename)

    def download_zip(self, filename=None):
        if filename is None:
            filename = 'download_sei.zip'
        self._download(filetype='zip', filename=filename)

    def _download(self, filetype, filename='download_sei.pdf'):
        url = [i for i in procSei.acoes if filetype in i][0]
        r = self.session.get(url)
        soup = self.get_soup(r.content)
        url_gera_pdf = URL_SEI + soup.find('form')['action']
        # params para o post
        params = {i['id']: i['value'] for
                  i in soup.find_all('input')[:-1]
                  if i.get('type', None) == 'hidden'}
        params['hdnFlagGerar'] = 1

        for n, item in enumerate(params['hdnInfraItens'].split(',')):
            params['chkInfraItem{}'.format(n)] = item
        r = self.session.post(url_gera_pdf, params)
        url_pdf = re.search('(?<=window.open\(\').*(?=\'\))', r.text).group()
        r = self.session.get(URL_SEI + url_pdf)
        DOWNLOAD_CONTENT = r.content

        if r.headers.get('Content-Disposition', None) is not None:
            filename = r.headers.get('Content-Disposition').split('"')[-2]

        with open(filename, 'wb') as f:
            f.write(DOWNLOAD_CONTENT)

    @property
    def documentos(self):
        docs = {}
        for i in self._documentos:
            doc = Documento(self.session, i)
            docs[doc.number] = doc
        return docs


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
        r = self.session.get(url_pesquisa)
        self.html = r.text

    def pesquisa(self, query='', nu_sei='', doc_gerados=True,
                 doc_recebidos=True, com_tramitacao=False):
        self.acessa_tela_pesquisa()

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

        soup = BeautifulSoup(self.html, 'lxml')
        url_pesquisa = soup.find('form', {'id': 'frmPesquisaProtocolo'})['action']

        r = self.session.post(self.url + url_pesquisa, data=data,
                              allow_redirects=False)
        processo_SEI = r.headers.get('Location', None)
        if processo_SEI:
            url_dados_processo = self.url + r.headers['Location']
            r = self.session.get(url_dados_processo)
            return ProcessoSei(self.session, r.text)
        else:
            return ResultadoPesquisa(self.session, r.text)
