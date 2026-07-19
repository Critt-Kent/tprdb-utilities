import os
import re
import numpy as np
import pandas as pd

# compute entropy values 
def ST_entropy_df(DF, Verbose = 1) :
    """
    Computes and aggregates entropy values for source texts across multiple study sessions.

    Parameters:
    -----------
    DF : pandas.DataFrame
        The input dataset containing at least 'Session' and source text data.
    Verbose : int, optional (default=1)
        Controls the logging verbosity level. 1 prints status/warnings, 0 suppresses them.

    Returns:
    --------
    pandas.DataFrame
        A single concatenated DataFrame containing the merged entropy metrics and 
        original session details for all valid source texts.
    """
    
    # Group and map unique session identifiers to their corresponding text IDs
    STfiles = _SortTextsInStudy_df(DF['Session'].unique())

    L = []
    # Iterate through each unique text ID found in the study    
    for textID in STfiles:

        # Retrieve cumulative counts (HTRA) and session-specific tables for the text ID
        HTRA, STables, Error = _ST_countValues_df(DF, STfiles[textID], Verbose = Verbose)

         # Skip processing if the sessions contain mismatched source text versions
        if(Error) : 
            print(f"ERROR: different Source Texts {textID} : Entropy values cannot be added!")
            continue

            
        if(Verbose) : 
            cnt = 0
            if (1 in HTRA) : cnt = HTRA[1]['cnt']
                
            print(f"Source Texts {textID} with instances {cnt} ")
            
        # Calculate raw entropy metrics from the aggregated token counts
        SCcolumns = _ST_entropy_values(HTRA)

        # Process and merge entropy results back into each individual session table
        for session in STables:
            # Ensure the session has calculated entropy columns available
            if(session not in SCcolumns):
                print("Warning ST_entropy:", session)
                continue

            # Convert the session's entropy dictionary to a DataFrame and transpose it
            df = pd.DataFrame(SCcolumns[session]).T

            # Extract metric column names, preserving 'SToken' for the upcoming merge
            cols = list(df.columns)
            if('SToken' in cols) : cols.remove('SToken')

            # Clean the source table by removing existing duplicate or suffixed metric columns
            df2 = STables[session].drop(columns=cols, errors='ignore')
            df2 = df2.drop(columns=[f"{c}_x" for c in cols], errors='ignore')
            df2 = df2.drop(columns=[f"{c}_y" for c in cols], errors='ignore')

            # Merge the original data with new entropy features on tracking identifiers
            df['Id'] = range(1, len(df) +1)

            # and merge
            L.append(pd.merge(df2, df, on=['Id', 'SToken'], how='inner'))

    # Combine all individual session DataFrames into a single study-wide master dataset
    return pd.concat(L)


# Compute entopy for segments
def SG_entropy_df(SG, ST, Verbose = 1) :
    """
    Computes and aggregates baseline entropy and information metrics for segment data.

    Processes sub-segments within a segment identifier (split by '+') and calculates 
    aggregated statistical properties (mean or sum) based on source token metrics.

    Parameters:
    -----------
    SG : pandas.DataFrame
        The target segment dataset to update with calculated entropy metrics.
    ST : pandas.DataFrame
        The source token dataset containing the reference entropy metrics.
    Verbose : int, optional (default=1)
        Controls logging granularity. Values > 2 enable session-by-session tracking.

    Returns:
    --------
    pandas.DataFrame
        The modified SG DataFrame with populated 'HTot', 'HTraN', 'InfS', and 'InfT' columns.
    """
    
    # Enforce matching string data types on segment keys to prevent merging mismatches
    # make sure STseg is of same type
    ST['STseg'] = ST['STseg'].astype(str)
    SG['STseg'] = SG['STseg'].astype(str)

    # initialize entropy values
    SG['HTot'] = 0.0
    SG['HTraN'] = 0.0
    SG['InfS'] = 0.0
    SG['InfT'] = 0.0
    
    # Map unique session names to their text identifiers
    TextSessions = _SortTextsInStudy_df(SG['Session'].unique())

    # Process datasets tracking one distinct text identifier at a time
    for textID in TextSessions:

        if(Verbose) : print(f"Text Id:{textID}\tTexts:{len(TextSessions[textID])}")
            
        # Evaluate sessions assigned to the current text identifier sequentially
        for session in sorted(TextSessions[textID]) :

            if(Verbose > 2) : print(f"\t{session}")

            # Isolate segment records and token records belonging strictly to this session
            sg = SG[SG['Session'] == session]
            st = ST[ST['Session'] == session]
                
            # Iterate unique segment groupings present in this session slice
            for seg in set(sg.STseg) :

                # 1. Process Normalized Transition Entropy (HTraN)
                N = []
                # Break complex segment compounds down and gather related token values
                # accumulate HTraN values for segment
                for s in seg.split('+') : N.extend(st[st.STseg == s]['HTraN'])  
                    
                # Store the mathematical average of the collected metrics globally
                SG.loc[SG.STseg == seg, 'HTraN'] = np.mean(N) 
        
                # 2. Process Total Transition Entropy (HTot)
                N = []
                # accumulate HTra values for segment
                for s in seg.split('+') : N.extend(st[st.STseg == s]['HTra'])
                # and compute sum HTra
                SG.loc[SG.STseg == seg, 'HTot'] = np.sum(N) 
                
                # 3. Process Source Information metrics (InfS)
                N = []
                # accumulate InfS values for segment
                for s in seg.split('+') : N.extend(st[st.STseg == s]['InfS'])
                # and compute sum InfS
                SG.loc[SG.STseg == seg, 'InfS'] = np.mean(N) 
                
                # 4. Process Target Information metrics (InfT)                
                N = []
                # accumulate InfT values for segment
                for s in seg.split('+') : N.extend(st[st.STseg == s]['InfT'])
                # and compute sum InfT
                SG.loc[SG.STseg == seg, 'InfT'] = np.mean(N)
                
    return SG
        
def DF_entropy_df(DF, ST, Verbose = 1) :
    """
    Computes and aggregates entropy metrics for a DataFrame using source token  data.

    Maps compound source group token IDs ('SGid', split by '+') to matching source token IDs 
    ('STid') within identical sessions, calculating summary statistics (mean or sum).

    Parameters:
    -----------
    DF : pandas.DataFrame
        The primary study tracking dataset to update with calculated entropy metrics.
    ST : pandas.DataFrame
        The reference source token dataset containing granular entropy metrics.
    Verbose : int, optional (default=1)
        Controls logging detail. Levels > 1 flag unaligned or empty metrics tracking.

    Returns:
    --------
    pandas.DataFrame
        The updated DF DataFrame containing populated 'HTot', 'HTraN', 'InfS', and 'InfT' fields.
    """
    
    # Verify the existence of the critical structural 'SGid' column before processing    
    if ('SGid' not in DF) :
        print(f"DF_entropy_df-1: no SGid in DF: {DF.head(3)}")
        return DF
              
    # Initialize target metric receiver columns as floating points set to zero
    DF['HTot'] = 0.0
    DF['HTraN'] = 0.0
    DF['InfS'] = 0.0
    DF['InfT'] = 0.0
    
    # Establish top-level mapping connecting unique text IDs to their structural sessions
    # Map unique session names to their overarching text identifiers
    TextSessions = _SortTextsInStudy_df(DF['Session'].unique())

    # Cycle sequentially through each isolated text cluster in the current study
    for textID in TextSessions:

        if(Verbose) : print(f"Text Id:{textID}\tTexts:{len(TextSessions[textID])}")
            
        # Inspect separate recording sessions aligned to the active text identifier
        for session in sorted(TextSessions[textID]) :

            if(Verbose > 2) : print(f"\t{session}")
                
            # Create working isolated copies restricted to data matching this session
            df = DF[DF['Session'] == session]
            st = ST[ST['Session'] == session]
                
            # Perform sequential row-by-row tracking across the current session frame
            for index, unit in df.iterrows() :

                # Enforce string evaluation on the primary token compound indicator
                SGid = str(unit['SGid'])

                # Skip unaligned placeholders, unlinked content, or corrupted indices
                if (SGid == '---') or (SGid == '0'):
                    if(Verbose > 1) :print(f"DF_entropy_df: {unit['StudySession']}\tId:{unit['Id']} SGid: {SGid}")
                    continue
                            
                    
                N = []
                # accumulate HTraN values from STid for unit SGid 
                for s in SGid.split('+') : N.extend(st[st.STid == int(s)]['HTraN'])

                # 1. Process Normalized Transition Entropy (HTraN)
                if(N == []) :
                    print(f"DF_entropy_df-HTraN: {unit['StudySession']}\tId:{unit['Id']} SGid:{SGid} N:{N}")
                    continue
                      
                # Log the average behavior onto the master data record using index reference
                DF.loc[index, 'HTraN'] = np.mean(N) 
    
                # 2. Process Total Transition Entropy (HTot)
                N = []
                # accumulate HTra values for segment
                for s in SGid.split('+') : N.extend(st[st.STid == int(s)]['HTra'])
                if(N == []) :
                    print(f"DF_entropy_df-HTra: {unit['StudySession']}\tId:{unit['Id']} SGid:{SGid} N:{N}")
                    continue
                    
                # Compute cumulative absolute cost and write back directly to the row index
                DF.loc[index, 'HTot'] = np.sum(N) 
                
                # 3. Process Source Information metrics (InfS)
                N = []
                # accumulate InfS values for segment
                for s in SGid.split('+') : N.extend(st[st.STid == int(s)]['InfS'])
                if(N == []) :
                    print(f"DF_entropy_df-InfS: {unit['StudySession']}\tId:{unit['Id']} SGid:{SGid} N:{N}")
                    continue
                # and compute sum InfS
                DF.loc[index, 'InfS'] = np.mean(N) 
                
                # 4. Process Target Information metrics (InfT)
                N = []
                # accumulate InfT values for segment
                for s in SGid.split('+') : N.extend(st[st.STid == int(s)]['InfT'])
                if(N == []) :
                    print(f"DF_entropy_df-InfT: {unit['StudySession']}\tId:{unit['Id']} SGid:{SGid} N:{N}")
                    continue
                    
                # and compute sum InfT
                DF.loc[index, 'InfT'] = np.mean(N)
                
    return DF
    

# return a dictionary {text : [list_of_sessions] ... } 
def _SortTextsInStudy_df(sessions) :
    """
    sessions: list of sessions
    
    """
        
    # store the list of sessions per source textId 
    # e.g.: Study[1][session1, session5 ...]
    Study = {} 

    # find how many versions per ST 
    for fn in sessions:

        session = os.path.basename(fn)
        
        # parse the filename
        match = re.search(r'_[^\d]+(\d+)', session)
        if(match) :
            # convert to int, text could be 1 or 01
            tid = int(match.group(1))
            Study.setdefault(tid, [])      
            # parse the filename 
            Study[tid].append(session)
        else:
            print("TextIdsInStudy:filename:", fn)
        
    return Study



# per ST word count values for translation, TT group, ST group 
def _ST_countValues_df(DF, StudyTextID, Verbose = 0) :
    
    STable = {} # dictionary of sessions with dataframe
    HTRA = {}  # dictionary of text IDs with item counts
    ERR = {}
    for session in sorted(StudyTextID) :

        # pull out session and count frequency of items
        STable[session] = DF[DF['Session'] == session]
        
        for t in STable[session].itertuples() :
            HTRA.setdefault(t.Id, {})
            
            # check whether ST words are identical across texts
            if('ST' in HTRA[t.Id] and HTRA[t.Id]['ST'] != t.SToken) :
                if(Verbose > 2) : print(f"ERROR: Different ST texts: {fn}: seg:{t.STseg} STid:{t.STid} SToken:{t.SToken:<10}\t{HTRA[t.Id]['ST']} ")
                ERR.setdefault(session, set())
                ERR[session] = ERR[session].union({t.STseg}) 
            HTRA[t.Id]['ST'] = t.SToken
            HTRA[t.Id].setdefault('cnt', 0)
            HTRA[t.Id]['cnt'] += 1
            
            # Target Group (Translation) count
            HTRA[t.Id].setdefault('T', {})
            HTRA[t.Id]['T'].setdefault(t.TGroup, {})
            HTRA[t.Id]['T'][t.TGroup].setdefault('cnt', 0)
            HTRA[t.Id]['T'][t.TGroup]['cnt'] += 1
            HTRA[t.Id]['T'][t.TGroup].setdefault('sess', [])
            HTRA[t.Id]['T'][t.TGroup]['sess'].append(session)

            # Source Group count
            HTRA[t.Id].setdefault('S', {})
            HTRA[t.Id]['S'].setdefault(t.SGroup, {})
            HTRA[t.Id]['S'][t.SGroup].setdefault('cnt', 0)
            HTRA[t.Id]['S'][t.SGroup]['cnt'] += 1
            HTRA[t.Id]['S'][t.SGroup].setdefault('sess', [])
            HTRA[t.Id]['S'][t.SGroup]['sess'].append(session)

            #  Cross
            HTRA[t.Id].setdefault('C', {})
            HTRA[t.Id]['C'].setdefault(t.Cross, {})
            HTRA[t.Id]['C'][t.Cross].setdefault('cnt', 0)
            HTRA[t.Id]['C'][t.Cross]['cnt'] += 1
            HTRA[t.Id]['C'][t.Cross].setdefault('sess', [])
            HTRA[t.Id]['C'][t.Cross]['sess'].append(session)

            # Joint Source, Target, Cross
            STC = f"{t.SGroup}@@{t.TGroup}@@{t.Cross}"
            HTRA[t.Id].setdefault('STC', {})
            HTRA[t.Id]['STC'].setdefault(STC, {})
            HTRA[t.Id]['STC'][STC].setdefault('cnt', 0)
            HTRA[t.Id]['STC'][STC]['cnt'] += 1
            HTRA[t.Id]['STC'][STC].setdefault('sess', [])
            HTRA[t.Id]['STC'][STC]['sess'].append(session)

    for session in ERR:
        print(f"ERROR: different ST in: {session} : seg:{ERR[session]}")
        
    return (HTRA, STable, len(ERR) != 0)

def _ST_entropy_values(HTRA) :
    
    # compute information values and entropy
    for tId in HTRA:
        
        # loop over every word
        for item in HTRA[tId]['T']:
            HTRA[tId]['T'][item]['P'] = HTRA[tId]['T'][item]['cnt'] / HTRA[tId]['cnt']
            HTRA[tId]['T'][item]['I'] = np.log(1/HTRA[tId]['T'][item]['P']) 
            HTRA[tId].setdefault('HTra', 0)
            # Target-group Entropy 
            HTRA[tId]['HTra'] += HTRA[tId]['T'][item]['P']  *  HTRA[tId]['T'][item]['I']
            
        for item in HTRA[tId]['S']:
            HTRA[tId]['S'][item]['P'] = HTRA[tId]['S'][item]['cnt'] / HTRA[tId]['cnt']
            HTRA[tId]['S'][item]['I'] = np.log(1/HTRA[tId]['S'][item]['P']) 
            HTRA[tId].setdefault('HSgrp', 0)
            # Source-group Entropy 
            HTRA[tId]['HSgrp'] += HTRA[tId]['S'][item]['P']  *  HTRA[tId]['S'][item]['I']
        
            
        for item in HTRA[tId]['C']:
            HTRA[tId]['C'][item]['P'] = HTRA[tId]['C'][item]['cnt'] / HTRA[tId]['cnt']
            HTRA[tId]['C'][item]['I'] = np.log(1/HTRA[tId]['C'][item]['P']) 
            HTRA[tId].setdefault('HCross', 0)
            # Cross Entropy 
            HTRA[tId]['HCross'] += HTRA[tId]['C'][item]['P']  *  HTRA[tId]['C'][item]['I']
            
        for item in HTRA[tId]['STC']:
            HTRA[tId]['STC'][item]['P'] = HTRA[tId]['STC'][item]['cnt'] / HTRA[tId]['cnt']
            HTRA[tId]['STC'][item]['I'] = np.log(1/HTRA[tId]['STC'][item]['P']) 
            HTRA[tId].setdefault('HSTC', 0)
            # joint Sgroup, Tgroup, Cross  Entropy 
            HTRA[tId]['HSTC'] += HTRA[tId]['STC'][item]['P']  *  HTRA[tId]['STC'][item]['I']

    #AltT    CountT  ProbT   HTra    AltS    ProbS   HSgrp   AltC    ProbC   HCross  AltSTC  ProbSTC HSTC
    # mapping type - entropy attribute
    E = {'T':'HTra', 'S':'HSgrp', 'C':'HCross', 'STC':'HSTC'}
    M = {}
    for tId in HTRA:
        SToken = HTRA[tId]["ST"]
        
        for tpe in E.keys(): 

            for item in HTRA[tId][tpe]:
                for s in HTRA[tId][tpe][item]['sess'] :
                    M.setdefault(s, {})
                    M[s].setdefault(tId, {})
                    M[s][tId]["SToken"] = SToken
                    M[s][tId][f"Count"] = HTRA[tId][tpe][item]['cnt'] 
                    M[s][tId][f"Alt{tpe}"] = len(HTRA[tId][tpe].keys())
                    M[s][tId][f"Prob{tpe}"] = HTRA[tId][tpe][item]['P']
                    M[s][tId][f"Inf{tpe}"] = HTRA[tId][tpe][item]['I']
                    M[s][tId][E[tpe]] = HTRA[tId][E[tpe]]
                    # normalized Entropy
                    M[s][tId][f"{E[tpe]}N"] = HTRA[tId][E[tpe]] *np.log(2)/np.log(HTRA[tId]['cnt']) 
                    
    return M
