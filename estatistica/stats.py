import os

import pandas as pd
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def clica_menu_pesquisar():
    menu = wait.until(EC.presence_of_element_located((By.ID, "main-menu")))
    menu_pesquisar = menu.find_elements_by_tag_name('li')[3]
    menu_pesquisar.click()

def critica_nu_proc(nu_proc):
    if nu_proc == '' or (len(nu_proc) in (12, 14, 15, 17) is False) or pd.isnull(nu_proc):
        return False
    else:
        return True

URL_SEI = 'https://seimp.planejamento.gov.br/sei/'
driver = Chrome()
driver.get(URL_SEI)

wait = WebDriverWait(driver, 2)
field_cpf = wait.until(EC.presence_of_element_located((By.ID, "txtUsuario")))
field_senha = wait.until(EC.presence_of_element_located((By.ID, "pwdSenha")))
btn_acessar = wait.until(EC.presence_of_element_located((By.ID, "sbmLogin")))

nu_cpf = '05966258635'
nu_senha = 'julia0.6'

field_cpf.send_keys(nu_cpf)
field_senha.send_keys(nu_senha)
btn_acessar.click()

clica_menu_pesquisar()

converters = {'nu_processo_adm_inclusao': str, 'nu_resp': str}
processos_SEI = pd.read_csv('responsaveis-sem-cpf.csv', sep=';', converters=converters)
processos_SEI['nu_proc_valido'] = processos_SEI.nu_processo_adm_inclusao.map(critica_nu_proc)
processos_SEI = processos_SEI.drop_duplicates(subset='nu_processo_adm_inclusao').reset_index()

# filtra os processos já trabalhados em pesquisas anteriores
if os.path.isfile('processos_rip_pesquisa.csv'):
    resultados = pd.read_csv('processos_rip_pesquisa.csv', sep=';', header=None, converters={0: str})
    processos_SEI = processos_SEI[~processos_SEI.nu_processo_adm_inclusao.isin(resultados[0])]


print('Pesquisando', len(processos_SEI), 'processos.')
print('-' * 80)

nlocalizados = 0
for n, i in enumerate(processos_SEI.itertuples(), 1):
    nu_processo = i.nu_processo_adm_inclusao
    if i.nu_proc_valido is False:
        possui_processo = False
    else:
        campo_txt_pesquisa = wait.until(EC.presence_of_element_located((By.ID, 'txtProtocoloPesquisa')))
        campo_txt_pesquisa.clear()
        campo_txt_pesquisa.send_keys(nu_processo)

        btn_pesquisar = wait.until(EC.presence_of_element_located((By.ID, "sbmPesquisar")))
        btn_pesquisar.click()

        try:
            doc_externo = wait.until(EC.presence_of_element_located((By.ID, "conteudo")))
            possui_processo = False
        except TimeoutException:
            possui_processo = True
            retorna = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "infraImg")))
            retorna.click()
            clica_menu_pesquisar()

    processos_SEI.loc[i.Index, 'possui_processo'] = possui_processo

    with open('processos_rip_pesquisa.csv', 'a') as f:
        f.write(';'.join([nu_processo, str(possui_processo)]) + '\n')

    if possui_processo:
        nlocalizados += 1

    performance = str(round(nlocalizados / n * 100, 2))
    print(n, nu_processo.zfill(17), str(possui_processo).rjust(5, ' '), performance)
